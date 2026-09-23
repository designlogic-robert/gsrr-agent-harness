"""HC-01: immutable terminal attempts and separately guarded fresh allocation."""
from dataclasses import replace
from .contracts import Attempt, ScopeLedger, ControlPayload, Control, Gate, Mode
from .journal import RetentionError


class Supervisor:
    def __init__(self, journal, policy):
        self.journal = journal
        self.policy = policy
        self.attempts: tuple[Attempt, ...] = ()
        self.ledger: ScopeLedger | None = None
        self.approval = None
        self.envelope = None
        self.failure_refs: dict[str, str] = {}
        self.schedules: dict[str, Attempt] = {}
        self.effect_posture = "NONE_ESTABLISHED"
        self.last_control = Control.PASS
        if policy is not None:
            journal.retain(policy.policy_id, policy)

    @property
    def current(self):
        return self.attempts[-1] if self.attempts else None

    def remember_ledger(self):
        if self.ledger is not None:
            self.journal.retain(self.journal.new_id("scope-ledger"), self.ledger)

    def emit(self, kind, event_type, control, refs=(), checks=(), reason="",
             attempt=None, before=None, after=None, scheduled=None):
        a = attempt or self.current
        ledger = self.ledger
        policy = self.policy
        payload = ControlPayload(
            kind, refs, a.failure_class if a else None,
            ("PLAN_ENVELOPE",) if a and a.failure_class == "GENERATED_PLAN_ENVELOPE_VIOLATION" else (),
            (reason,), Gate.REFUSED if control in (
                Control.FAIL_NONRETRYABLE, Control.REJECT_RETRYABLE, Control.CIRCUIT_OPEN
            ) else Gate.HELD if control != Control.PASS else Gate.PASS,
            control, a.terminal if a else False,
            ledger.scope_ref if ledger else None, policy.policy_id if policy else None,
            before, after, policy.max_attempts if policy else None,
            ledger.circuit_state if ledger else "CLOSED", checks, checks,
            self.approval.approval_id if self.approval else None,
            self.envelope.envelope_id if self.envelope else None, checks,
            ledger.admission_seen if ledger else False, self.effect_posture, scheduled,
            "CIRCUIT_INVESTIGATION" if control == Control.CIRCUIT_OPEN else
            "AUTHORIZATION" if control == Control.HUMAN_AUTHORIZATION_REQUIRED else
            "JUDGMENT" if control == Control.HOLD_AMBIGUOUS else None,
        )
        self.last_control = control
        return self.journal.event(
            event_type, refs, control.value, reason, attempt=a,
            transition=self.envelope.transition_id if self.envelope else None,
            source_version=self.envelope.source_authority_version if self.envelope else None,
            observed_version=self.envelope.source_observation_version if self.envelope else None,
            policy=policy.policy_id if policy else None, payload=payload,
        )

    def start(self):
        if self.attempts:
            raise RetentionError("initial attempt already exists")
        a = Attempt(self.journal.new_id("attempt"), 1, None)
        self.attempts = (a,)
        self.journal.retain(a.attempt_id, a)
        self.emit("ATTEMPT_START", "AttemptStarted", Control.PASS,
                  (a.attempt_id,), reason="NOT_YET_CREATED: parent, approval, envelope and scope")
        return a

    def bind(self, approval, envelope):
        if self.ledger is not None:
            raise RetentionError("scope already bound")
        self.approval, self.envelope = approval, envelope
        ref = self.journal.new_id("scope")
        self.journal.retain(ref, (self.journal.run_id, envelope.transition_id,
                                  approval.approval_id, envelope.envelope_id))
        self.ledger = ScopeLedger(ref, self.policy.policy_id if self.policy else "",
                                  1, self.current.attempt_id)
        self.remember_ledger()
        self.emit("ATTEMPT_START", "AttemptStarted", Control.PASS,
                  (self.current.attempt_id, ref, approval.approval_id, envelope.envelope_id),
                  reason="SCOPE_BOUND: same initial attempt counted once",
                  before=0, after=1)

    def fail(self, control, failure_class, refs=(), retain=True):
        a = self.current
        if a is None or a.terminal:
            return
        terminal = replace(a, terminal=True, failure_class=failure_class)
        self.attempts = self.attempts[:-1] + (terminal,)
        self.journal.retain(a.attempt_id + ":terminal", terminal)
        if self.ledger:
            self.ledger = replace(self.ledger, active_attempt_id=None)
            self.remember_ledger()
        event = self.emit("TERMINAL_FAILURE",
                          "TransitionHeld" if control in (
                              Control.HOLD_AMBIGUOUS, Control.HUMAN_AUTHORIZATION_REQUIRED
                          ) else "TransitionRefused",
                          control, refs, reason=failure_class)
        if retain:
            self.failure_refs[a.attempt_id] = event.event_id
        else:
            self.last_control = Control.HOLD_AMBIGUOUS

    def admission(self):
        l = self.ledger
        if (l is None or self.current.terminal or l.active_attempt_id != self.current.attempt_id
                or l.circuit_state != "CLOSED" or not l.scheduling_known
                or l.admission_seen is not False):
            raise RetentionError("attempt cannot be admitted")
        self.ledger = replace(l, admission_seen=True)
        self.remember_ledger()

    def successor(self, prior_id, mode, fresh_control, check_refs=(),
                  scheduling_failure=False):
        # Re-consuming a retained allocation can only retrieve that same identity.
        if prior_id in self.schedules:
            return self.schedules[prior_id]
        a, l, p = self.current, self.ledger, self.policy
        if a is None or a.attempt_id != prior_id or not a.terminal or l is None:
            self.last_control = Control.FAIL_NONRETRYABLE
            return None
        control = Control.PASS
        if l.admission_seen is None or self.effect_posture == "UNKNOWN":
            control = Control.HOLD_AMBIGUOUS
        elif l.admission_seen or self.effect_posture != "NONE_ESTABLISHED":
            control = Control.FAIL_NONRETRYABLE
        elif mode != Mode.EXPLICIT_PLAN or a.failure_class != "GENERATED_PLAN_ENVELOPE_VIOLATION":
            control = Control.FAIL_NONRETRYABLE
        elif p is None or not p.valid() or prior_id not in self.failure_refs:
            control = Control.HOLD_AMBIGUOUS
        elif p.policy_id != l.policy_ref or self.journal.get(l.policy_ref) != p:
            control = Control.HOLD_AMBIGUOUS
        elif not p.retry_enabled or a.failure_class not in p.allowed_failure_classes:
            control = Control.FAIL_NONRETRYABLE
        elif not l.scheduling_known or l.active_attempt_id or l.scheduled_attempt_id:
            control = Control.HOLD_AMBIGUOUS
        elif fresh_control != Control.PASS:
            control = fresh_control
        elif not check_refs:
            control = Control.HOLD_AMBIGUOUS
        refs = (self.failure_refs[prior_id],) if prior_id in self.failure_refs else ()
        if control != Control.PASS:
            self.emit("RETRY_ELIGIBILITY", "RetryEligibilityDetermined", control,
                      refs, check_refs, "no eligible successor")
            return None
        self.emit("RETRY_ELIGIBILITY", "RetryEligibilityDetermined",
                  Control.REJECT_RETRYABLE, refs, check_refs, "eligible fresh plan only")
        failures = sum(x.terminal and x.failure_class == a.failure_class for x in self.attempts)
        threshold = p.repeated_failure_threshold_or_null
        if (l.circuit_state == "OPEN" or l.attempts_created >= p.max_attempts
                or threshold is not None and failures >= threshold):
            self.ledger = replace(l, circuit_state="OPEN")
            self.remember_ledger()
            self.emit("CIRCUIT_OPEN", "CircuitOpened", Control.CIRCUIT_OPEN,
                      refs, check_refs, "finite attempt budget or failure threshold",
                      before=l.attempts_created, after=l.attempts_created)
            self.emit("HUMAN_ESCALATION", "HumanEscalationRequired", Control.CIRCUIT_OPEN,
                      refs, reason="immediate investigation; no automatic circuit reset")
            return None
        if scheduling_failure:
            self.ledger = replace(l, scheduling_known=False)
            self.remember_ledger()
            self.emit("RETRY_ELIGIBILITY", "RetryEligibilityDetermined", Control.HOLD_AMBIGUOUS,
                      refs, check_refs, "scheduling retention unavailable; no refund or alternate allocation")
            return None
        new = Attempt(self.journal.new_id("attempt"), l.attempts_created + 1, a.attempt_id)
        # The synchronous fixture admits no intervening mutation between checks and allocation.
        self.journal.retain(new.attempt_id, new)
        self.emit("NEW_ATTEMPT_AUTHORIZATION", "NewAttemptAuthorized", Control.PASS,
                  refs + (new.attempt_id,), check_refs, "creation only; no execution permission",
                  attempt=a, before=l.attempts_created, after=l.attempts_created + 1,
                  scheduled=new.attempt_id)
        self.ledger = replace(l, attempts_created=l.attempts_created + 1,
                              active_attempt_id=new.attempt_id)
        self.attempts += (new,)
        self.emit("ATTEMPT_START", "AttemptStarted", Control.PASS,
                  (new.attempt_id,), reason="distinct fresh successor",
                  before=l.attempts_created, after=l.attempts_created + 1)
        self.remember_ledger()
        self.schedules[prior_id] = new
        return new
