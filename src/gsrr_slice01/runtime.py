"""Readable top-level orchestration for one closed-fixture operation scope."""
from dataclasses import dataclass, replace
from .contracts import (
    AuthorityEvidence, RetryPolicy, Mode, Control, RealizationCommit, ExecutionResult,
    ReconciliationResult, ProjectionDecision, Definition, ExecutionPlan,
    PlanValidationResult, StructuredIntent, CandidateTransition, CandidateSelection,
    TransitionValidationResult, ApprovedTransition, Gate, DispatchPayload,
    Report, Outcome, plain,
)
from .fixture import Provider, Capability, RequestPort, FixtureFaults
from .journal import Journal, RetentionError
from .governance import (
    PROFILE, ExplicitPlanner, check, grant_check, descriptor, envelope,
    build_instruction, validate_plan,
)
from .retry import Supervisor
from .reconciliation import reconcile, project


@dataclass(frozen=True)
class Request:
    request_id: str = "request-1"
    actor_id: str = "USER-001"
    object_id: str = "DOC-001"
    target_state: str = "REVIEW"
    mode: Mode = Mode.EXPLICIT_PLAN


@dataclass(frozen=True)
class RunResult:
    disposition: str
    control: Control
    commit: RealizationCommit | None
    execution: ExecutionResult | None
    reconciliation: ReconciliationResult | None
    projection: ProjectionDecision | None


@dataclass(frozen=True)
class RetainedRequest:
    request: Request
    binding: tuple
    result: RunResult | None


class SliceRuntime:
    def __init__(self, *, run_id="run-1", definition=None, grant=AuthorityEvidence(),
                 policy=RetryPolicy(), faults=FixtureFaults()):
        self.journal = Journal(run_id)
        self.definition = definition or Definition()
        self.original_definition = self.definition
        self.grant = grant
        self.policy = policy
        self.faults = faults
        self.provider = Provider(self.journal)
        self.capability = Capability()
        self.planner = ExplicitPlanner()
        self.control = Control.PASS
        self.before = self.baseline = self.intent = self.transition = None
        self.approval = self.envelope = self.plan = self.plan_validation = None
        self.commit = self.execution = self.reconciliation = self.projection = None
        self.observed = None
        self.plans: tuple[ExecutionPlan, ...] = ()
        self.validations: tuple[PlanValidationResult, ...] = ()
        self.index: dict[str, RetainedRequest] = {}
        self.dispatch_claims: set[str] = set()
        self._injected: set[tuple[str, str]] = set()
        self.current_read_fault = ""
        self.journal.retain(self.definition.definition_id, self.definition)
        self.retain_grant()
        for ref in (
            PROFILE, "selection-policy", "environment", "fixture-boundary",
            "fixed-input-contract", "authority-contract", "action-observation-contract",
            "STATE_PROVIDER", "USER-001", "fixture-issuer", "fixture-human-issuer",
            "SUBMIT_FOR_REVIEW", "fixture.submit_for_review.v0_1",
            "PLAN_ENVELOPE", "AUTHORITY", "HUMAN_SUBJECT", "ENVELOPE_DERIVATION",
            "FRESH_STATE", "NO_ADMISSION_OR_EFFECT", "ACTION_COMPLETENESS", "NO_FORBIDDEN_ACTION",
            "CURRENT_AUTHORITY", "ATTRIBUTION", "TARGET_POSTCONDITIONS",
            "INVOCATION_BINDING", "FINAL_READ", "TRANSITION_VALIDITY", "DOC-001",
        ):
            self.journal.retain(ref, ("SUPPLIED_FIXTURE_RULE_OR_IDENTITY", ref))
        self.cap_descriptor = descriptor(self.journal, self.definition)
        self.supervisor = Supervisor(self.journal, policy)

    def retain_grant(self):
        if self.grant is not None:
            self.journal.retain(self.grant.evidence_id, self.grant)
            if self.grant.policy_ref:
                self.journal.retain(self.grant.policy_ref, ("SUPPLIED_HUMAN_POLICY",))

    def stop(self, control, reason, refs=()):
        self.control = control
        self.supervisor.fail(control, reason, refs)
        return self.result()

    def result(self, disposition="TERMINAL"):
        return RunResult(disposition, self.control, self.commit, self.execution,
                         self.reconciliation, self.projection)

    def inject(self, seam):
        """Only named deterministic test seams; no handler-controlled callback."""
        for entry in self.faults.injections:
            where, kind = entry
            if where != seam or entry in self._injected:
                continue
            self._injected.add(entry)
            if kind in ("authority", "observation", "content"):
                self.provider.external_change(kind)
            elif kind in ("grant_inactive", "grant_unknown", "human_reserved", "approval_subject"):
                self.grant = replace(
                    self.grant or AuthorityEvidence(),
                    evidence_id=self.journal.new_id("grant"),
                    active=None if kind == "grant_unknown" else False if kind == "grant_inactive" else True,
                    human_required=kind in ("human_reserved", "approval_subject"),
                    subject_ref="different-immutable-subject" if kind == "approval_subject" else None,
                    decision="APPROVE" if kind == "approval_subject" else None,
                    human_issuer="fixture-human-issuer" if kind == "approval_subject" else None,
                    policy_ref="human-policy" if kind in ("human_reserved", "approval_subject") else None,
                )
                self.retain_grant()
            elif kind == "definition":
                self.definition = replace(self.definition, definition_version=2)
            elif kind == "missing_read":
                self.current_read_fault = "missing"
            elif kind in ("admitted", "unknown_admission"):
                self.supervisor.ledger = replace(
                    self.supervisor.ledger, admission_seen=True if kind == "admitted" else None)
                self.supervisor.remember_ledger()
            elif kind in ("possible_effect", "occurred_effect", "unknown_effect", "dispatch"):
                self.supervisor.effect_posture = {
                    "possible_effect": "POSSIBLE", "occurred_effect": "OCCURRED",
                    "unknown_effect": "UNKNOWN", "dispatch": "OCCURRED",
                }[kind]
            elif kind == "envelope":
                self.envelope = replace(self.envelope, target_state="APPROVED")
            elif kind == "plan_mode":
                self.plan = replace(self.plan, realization_mode=Mode.DELEGATED_REALIZATION)
            elif kind == "target":
                self.transition = replace(self.transition, target_state="APPROVED")
            else:
                raise ValueError(f"unknown fixture seam injection: {kind}")

    def no_effect_check(self):
        """Retain this scope's pre-allocation facts inside the trusted local fixture."""
        ledger = self.supervisor.ledger
        ledger_ref = self.journal.new_id("retry-scope-ledger")
        self.journal.retain(ledger_ref, ledger)
        commits = tuple(ref for ref, record in self.journal.aggregate.records
                        if isinstance(record, RealizationCommit)
                        and record.execution_envelope_id == self.envelope.envelope_id)
        posture = self.supervisor.effect_posture
        facts = (
            ("scope_ref", ledger.scope_ref if ledger else None),
            ("scope_ledger_ref", ledger_ref),
            ("admission_seen", ledger.admission_seen if ledger else None),
            ("commit_refs", commits),
            ("dispatch_claims", tuple(sorted(self.dispatch_claims))),
            ("provider_invocations", self.provider.invocation_count),
            ("provider_current_invocation", self.provider.current_invocation),
            ("provider_actions", self.provider.actions),
            ("effect_posture", posture),
        )
        facts_ref = self.journal.new_id("retry-effect-facts")
        self.journal.retain(facts_ref, facts)
        unknown = ledger is None or ledger.admission_seen is None or posture == "UNKNOWN"
        clear = (ledger is not None and ledger.admission_seen is False
                 and not commits and not self.dispatch_claims
                 and self.provider.invocation_count == 0
                 and self.provider.current_invocation is None and not self.provider.actions
                 and posture == "NONE_ESTABLISHED")
        return check("NO_ADMISSION_OR_EFFECT", None if unknown else clear,
                     (ledger_ref, facts_ref, "fixture-boundary"),
                     "Before successor allocation in this scope: no admission or retained commit, "
                     "no dispatch claim or provider invocation, no actions, "
                     "effect posture NONE_ESTABLISHED required; trusted in-memory fixture only")

    def fresh(self, *, final=False, retry=False):
        effect_checks = (self.no_effect_check(),) if retry else ()
        observed = self.provider.observe(self.current_read_fault, initial=not final)
        snapshot = self.provider.snapshot(self.definition, observed) if observed else None
        refs = tuple(x.snapshot_id for x in (observed, snapshot) if x is not None)
        if observed is None or snapshot is None:
            return Control.HOLD_AMBIGUOUS, (check("FRESH_STATE", None, refs, "required read missing"),) + effect_checks, observed, snapshot
        e = self.envelope
        expected_obs = self.observed if final else self.baseline
        same = (
            snapshot.authority_version == self.before.authority_version
            and snapshot.state == self.before.state
            and observed.observation_version == expected_obs.observation_version
            and observed.state == expected_obs.state and observed.exists == expected_obs.exists
            and observed.content_digest == expected_obs.content_digest
            and self.definition == self.original_definition
            and self.journal.get(e.envelope_id) == e
            and self.journal.get(self.transition.transition_id) == self.transition
            and self.journal.get(self.approval.approval_id) == self.approval
            and e.target_state == self.transition.target_state == "REVIEW"
        )
        if final:
            same = same and observed.actions == self.observed.actions and (
                observed.action_log_ref == self.observed.action_log_ref
                and observed.interval_closed is True
                and observed.complete_for_invocation is True
                and observed.commit_id == self.observed.commit_id
            )
        checks = (check("FRESH_STATE", same, refs, "compare original state or reconciled history token"),) + effect_checks
        if not same:
            return Control.HOLD_AMBIGUOUS, checks, observed, snapshot
        plan_ref = "new-plan-not-yet-authorized" if retry else self.plan.plan_id if self.plan else None
        control, auth = grant_check(self.grant, self.definition, self.before.authority_version,
                                    self.intent.intent_id, plan_ref)
        if control == Control.PASS and effect_checks and effect_checks[0].result != "PASS":
            control = (Control.HOLD_AMBIGUOUS if effect_checks[0].result == "UNRESOLVED"
                       else Control.FAIL_NONRETRYABLE)
        return control, checks + auth, observed, snapshot

    def prepare(self, request=Request()):
        """Produce immutable approved WHAT, before either HOW path."""
        if self.supervisor.attempts:
            raise RetentionError("request already prepared")
        self.request = request
        self.supervisor.start()
        if self.policy is None or not self.policy.valid():
            self.stop(Control.HOLD_AMBIGUOUS, "INVALID_RETRY_POLICY")
            return False
        self.intent = StructuredIntent(
            **self.journal.common("GSRR_SLICE_01"), intent_id=request.request_id,
            actor_id="" if self.faults.missing_intent else request.actor_id,
            object_type="Document", object_id=request.object_id,
            objective="Submit document for review", requested_target_state=request.target_state,
            unresolved_fields=("actor_id",) if self.faults.missing_intent else (),
            sufficiency_policy_ref=PROFILE,
        )
        self.journal.retain(self.intent.intent_id, self.intent)
        self.journal.event("IntentStructured", (self.intent.intent_id,), attempt=self.supervisor.current)
        if self.intent.unresolved_fields or self.faults.missing_profile:
            self.stop(Control.HOLD_AMBIGUOUS, "MISSING_INPUT_OR_PROFILE", (self.intent.intent_id,))
            return False
        self.inject("initial")
        self.baseline = self.provider.observe("missing" if self.faults.initial_read_missing else "", initial=True)
        if self.baseline is None:
            self.stop(Control.HOLD_AMBIGUOUS, "MISSING_INITIAL_STATE")
            return False
        self.before = self.provider.snapshot(self.definition, self.baseline)
        self.transition = CandidateTransition(
            **self.journal.common("GSRR_SLICE_01"), transition_id=self.journal.new_id("transition"),
            intent_id=self.intent.intent_id, snapshot_id=self.before.snapshot_id,
            object_id=request.object_id, source_state=self.before.state,
            source_authority_version=self.before.authority_version,
            source_observation_version=self.baseline.observation_version,
            target_state=request.target_state, definition_ref=self.definition.definition_id,
            rationale="supplied bounded objective", unresolved_fields=(),
        )
        self.journal.retain(self.transition.transition_id, self.transition)
        self.journal.transition_ref = self.transition.transition_id
        self.journal.source_version = self.before.authority_version
        self.journal.observed_version = self.baseline.observation_version
        candidates = (self.transition.transition_id,)
        if self.faults.candidate_count == 0:
            candidates = ()
        elif self.faults.candidate_count > 1:
            other = replace(self.transition, transition_id=self.journal.new_id("transition"))
            self.journal.retain(other.transition_id, other)
            candidates += (other.transition_id,)
        eligible = len(candidates) == 1 and not self.faults.selection_unknown
        selected = CandidateSelection(
            **self.journal.common("PCPK"), selection_id=self.journal.new_id("selection"),
            considered_transition_ids=candidates,
            selected_transition_id_or_null=self.transition.transition_id if eligible else None,
            selection_policy_ref="selection-policy", environment_ref="environment",
            selection_eligible=None if self.faults.selection_unknown else eligible,
            disposition="SELECTED" if eligible else "NO_SELECTION",
            reasons=("supplied one-candidate predicate",),
            unresolved_fields=() if eligible else ("selection",), sufficiency_policy_ref=PROFILE,
        )
        self.journal.retain(selected.selection_id, selected)
        if not eligible:
            self.stop(Control.HOLD_AMBIGUOUS, "NO_SELECTION", (selected.selection_id,))
            return False
        self.journal.event("CandidateSelected", (selected.selection_id,), attempt=self.supervisor.current)
        valid = (
            request.actor_id == "USER-001" and request.object_id == "DOC-001"
            and request.target_state == "REVIEW" and self.before.state == self.baseline.state == "DRAFT"
            and self.baseline.exists and self.before.exists
            and self.baseline.content_digest == self.before.content_digest
        )
        validation = TransitionValidationResult(
            **self.journal.common("DASA"), validation_id=self.journal.new_id("validation"),
            transition_id=self.transition.transition_id, snapshot_id=self.before.snapshot_id,
            definition_ref=self.definition.definition_id,
            checked_authority_version=self.before.authority_version,
            checked_observation_version=self.baseline.observation_version,
            check_results=(check("TRANSITION_VALIDITY", valid, (self.transition.transition_id,),
                                 "allowed edge and complete preconditions"),),
            disposition=Gate.PASS if valid else Gate.REFUSED, reasons=("fixture edge",),
        )
        self.journal.retain(validation.validation_id, validation)
        if not valid:
            self.stop(Control.FAIL_NONRETRYABLE, "INVALID_REQUESTED_WHAT", (validation.validation_id,))
            return False
        self.journal.event("TransitionValidated", (validation.validation_id,), attempt=self.supervisor.current)
        authority, checks = grant_check(self.grant, self.definition, self.before.authority_version,
                                        self.intent.intent_id)
        if authority != Control.PASS:
            self.stop(authority, "AUTHORITY_REQUIRED",
                      (validation.validation_id,) + self.record_checks(checks))
            return False
        self.approval = ApprovedTransition(
            **self.journal.common("DASA"), approval_id=self.journal.new_id("approval"),
            transition_id=self.transition.transition_id, validation_id=validation.validation_id,
            object_id=request.object_id, source_authority_version=self.before.authority_version,
            source_observation_version=self.baseline.observation_version,
            target_state=request.target_state, actor_id=request.actor_id,
            authority_evidence_refs=(self.grant.evidence_id,), definition_ref=self.definition.definition_id,
            authority_check_results=checks, disposition=Gate.PASS,
        )
        self.journal.retain(self.approval.approval_id, self.approval)
        self.journal.event("TransitionAuthorized", (self.approval.approval_id,), attempt=self.supervisor.current)
        self.envelope = envelope(self.journal, self.approval, self.transition, self.definition,
                                 self.before, self.baseline)
        self.supervisor.bind(self.approval, self.envelope)
        return True

    def record_checks(self, checks):
        ref = self.journal.new_id("checks")
        self.journal.retain(ref, checks)
        return (ref,)

    def realize(self, key="key-1", mode=None):
        if self.envelope is None or self.supervisor.current.terminal:
            return self.result()
        mode = mode or self.request.mode
        while True:
            a = self.supervisor.current
            defect = self.faults.plan_defects[a.attempt_number - 1] if (
                a.attempt_number <= len(self.faults.plan_defects)) else ""
            self.plan = self.planner.propose(self.journal, self.envelope, a.attempt_id, defect) if (
                mode == Mode.EXPLICIT_PLAN) else build_instruction(
                    self.journal, self.envelope, a.attempt_id, mode, defect)
            if self.plan is None:
                return self.stop(Control.HOLD_AMBIGUOUS, "PLAN_INFEASIBLE")
            self.plans += (self.plan,)
            self.plan_validation = validate_plan(
                self.journal, self.plan, self.envelope, self.approval, self.definition,
                self.cap_descriptor, a.attempt_id)
            self.validations += (self.plan_validation,)
            self.journal.event("ExecutionPlanValidated", (self.plan_validation.plan_validation_id,),
                               self.plan_validation.disposition.value, attempt=a)
            if self.plan_validation.disposition == Gate.PASS:
                break
            failure = "GENERATED_PLAN_ENVELOPE_VIOLATION" if (
                mode == Mode.EXPLICIT_PLAN and self.plan_validation.disposition == Gate.REFUSED
            ) else "NONELIGIBLE_PLAN_FAILURE"
            may_consider_retry = (
                failure == "GENERATED_PLAN_ENVELOPE_VIOLATION"
                and self.policy.retry_enabled
                and failure in self.policy.allowed_failure_classes
                and not self.faults.failure_evidence_missing
                and self.supervisor.ledger.admission_seen is False
                and self.supervisor.effect_posture == "NONE_ESTABLISHED"
            )
            self.supervisor.fail(
                Control.HOLD_AMBIGUOUS if self.plan_validation.disposition == Gate.HELD
                else Control.REJECT_RETRYABLE if may_consider_retry
                else Control.FAIL_NONRETRYABLE, failure,
                (self.plan_validation.plan_validation_id,),
                retain=not self.faults.failure_evidence_missing)
            if failure != "GENERATED_PLAN_ENVELOPE_VIOLATION":
                self.control = self.supervisor.last_control
                return self.result()
            self.inject("retry")
            control, checks, _, _ = self.fresh(retry=True)
            new = self.supervisor.successor(
                a.attempt_id, mode, control, self.record_checks(checks),
                self.faults.scheduling_failure)
            self.control = self.supervisor.last_control
            if new is None:
                return self.result()
        self.inject("pre_commit")
        control, checks, _, _ = self.fresh()
        if control != Control.PASS:
            return self.stop(control, "PRE_COMMIT_FRESHNESS", self.record_checks(checks))
        try:
            self.admit(key)
        except RetentionError:
            return self.stop(Control.HOLD_AMBIGUOUS, "COMMIT_RETENTION_OR_ACTIVE_ATTEMPT")
        return self.dispatch()

    def binding(self):
        e, p, v = self.envelope, self.plan, self.plan_validation
        return (self.approval.actor_id, self.intent.intent_id, e.transition_id, e.object_id,
                e.source_authority_version, e.source_observation_version, e.definition_ref,
                e.approval_id, e.envelope_id, p.plan_id, v.plan_validation_id,
                p.steps[0].capability_id, p.steps[0].implementation_id, p.realization_mode)

    def admit(self, key):
        if self.faults.commit_retention_failure:
            raise RetentionError("commit/event retention unavailable")
        if self.journal.get(self.plan.plan_id) != self.plan:
            raise RetentionError("immutable plan changed")
        if self.journal.get(self.plan_validation.plan_validation_id) != self.plan_validation:
            raise RetentionError("immutable validation changed")
        if self.plan_validation.disposition != Gate.PASS:
            raise RetentionError("plan not validated")
        if not (
            self.plan_validation.plan_id == self.plan.plan_id
            and self.plan_validation.envelope_id == self.envelope.envelope_id
            and self.plan_validation.approval_id == self.approval.approval_id
            and self.plan.envelope_id == self.envelope.envelope_id
            and self.plan.attempt_id == self.plan_validation.attempt_id
            == self.supervisor.current.attempt_id
        ):
            raise RetentionError("validation does not bind this exact active plan")
        self.supervisor.admission()
        j, e, p = self.journal, self.envelope, self.plan
        cid, eid = j.new_id("commit"), j.new_id("event")
        s = p.steps[0]
        f = s.fixed_input
        payload = DispatchPayload(f.object_id, f.source_state, f.target_state,
                                  f.expected_observation_version, s.capability_id,
                                  s.implementation_id, p.plan_id, e.envelope_id, cid, key, cid)
        commit = RealizationCommit(
            **j.common("GSRR_SLICE_01"), commit_id=cid, transition_id=e.transition_id,
            object_id=e.object_id, source_state_version=e.source_authority_version,
            source_observation_version=e.source_observation_version,
            target_state=e.target_state, execution_envelope_id=e.envelope_id,
            execution_plan_id=p.plan_id, plan_validation_id=self.plan_validation.plan_validation_id,
            authority_evidence_refs=e.authority_evidence_refs, idempotency_key=key,
            required_postconditions=e.postconditions, reconciliation_obligation=e.reconciliation_requirements,
            status="COMMITTED", event_ref=eid, definition_ref=e.definition_ref,
            actor_id=self.approval.actor_id, capability_id=s.capability_id,
            implementation_id=s.implementation_id, dispatch_payload=payload,
            attempt_id=self.supervisor.current.attempt_id,
        )
        j.retain(cid, commit)
        j.commit_ref = cid
        j.retain(cid + ":payload", payload)
        j.event("TransitionCommitted", (cid,), attempt=self.supervisor.current,
                transition=e.transition_id, commit=cid, source_version=e.source_authority_version,
                observed_version=e.source_observation_version, event_id=eid)
        self.commit = commit
        self.index[key] = RetainedRequest(self.request, self.binding(), None)

    def dispatch(self, presented=None):
        c = self.commit
        if c.idempotency_key in self.dispatch_claims:
            if (presented is not None and presented != c.dispatch_payload
                    or self.binding() != self.index[c.idempotency_key].binding):
                return RunResult("REFUSED_DUPLICATE", Control.FAIL_NONRETRYABLE,
                                 None, None, None, None)
            return self.lookup(c.idempotency_key, self.request)
        self.inject("pre_dispatch")
        payload = c.dispatch_payload if presented is None else presented
        substitution = self.faults.payload_substitution
        if substitution:
            if substitution == "extra":
                payload = plain(payload) | {"unapproved": "extra"}
            else:
                payload = replace(payload, **{substitution: "substituted"})
        expected = DispatchPayload(
            self.plan.steps[0].fixed_input.object_id,
            self.plan.steps[0].fixed_input.source_state,
            self.plan.steps[0].fixed_input.target_state,
            self.plan.steps[0].fixed_input.expected_observation_version,
            self.plan.steps[0].capability_id, self.plan.steps[0].implementation_id,
            self.plan.plan_id, self.envelope.envelope_id, c.commit_id,
            c.idempotency_key, c.commit_id)
        equal = (
            type(payload) is DispatchPayload and payload == c.dispatch_payload == expected
            and self.journal.get(c.commit_id) == c
            and self.journal.get(self.plan.plan_id) == self.plan
            and self.journal.get(self.envelope.envelope_id) == self.envelope
            and self.journal.get(c.plan_validation_id) == self.plan_validation
            and self.plan_validation.plan_id == self.plan.plan_id == c.execution_plan_id
            and self.plan_validation.envelope_id == self.envelope.envelope_id == c.execution_envelope_id
            and self.plan_validation.approval_id == self.approval.approval_id
            and c.attempt_id == self.plan.attempt_id == self.plan_validation.attempt_id
            and not self.supervisor.current.terminal
        )
        if not equal:
            return self.finish_index(self.stop(Control.FAIL_NONRETRYABLE, "DISPATCH_BINDING_MISMATCH"))
        control, checks, _, _ = self.fresh()
        if control != Control.PASS:
            return self.finish_index(self.stop(control, "PRE_DISPATCH_FRESHNESS", self.record_checks(checks)))
        if c.idempotency_key in self.dispatch_claims:
            return self.lookup(c.idempotency_key, self.request)
        self.dispatch_claims.add(c.idempotency_key)
        self.journal.retain(c.commit_id + ":dispatch-claim", (c.commit_id, c.idempotency_key))
        self.supervisor.effect_posture = "POSSIBLE"
        self.provider.open_interval(c.commit_id)
        port = RequestPort()
        error = None
        try:
            status = self.capability.invoke(self.plan.realization_mode,
                                            self.plan.steps[0].fixed_input, port, self.faults)
        except ValueError as exc:
            status, error = Report.FAILURE, str(exc)
        for action in port.requests:
            self.provider.apply(action, self.plan.steps[0].fixed_input,
                                self.faults.allow_invalid_writes)
        interval = self.provider.close_interval()
        self.supervisor.effect_posture = "UNKNOWN" if status == Report.UNKNOWN else (
            "OCCURRED" if self.provider.actions else "NONE_ESTABLISHED")
        eid = self.journal.new_id("event")
        self.execution = ExecutionResult(
            **self.journal.common("EXECUTOR"), result_id=self.journal.new_id("result"),
            commit_id=c.commit_id, plan_id=c.execution_plan_id, capability_id=c.capability_id,
            implementation_id=c.implementation_id, object_id=c.object_id,
            expected_observation_version=c.source_observation_version, dispatch_started=True,
            reported_status=status, error_or_null=error, idempotency_key=c.idempotency_key,
            event_ref=eid, invocation_id=c.commit_id,
            dispatched_payload_ref=c.commit_id + ":payload", action_interval_ref=interval,
        )
        self.journal.retain(self.execution.result_id, self.execution)
        self.journal.event("ExecutionCompleted", (self.execution.result_id,), status.value,
                           attempt=self.supervisor.current, commit=c.commit_id, event_id=eid)
        if status != Report.SUCCESS:
            self.stop(Control.HOLD_AMBIGUOUS if status == Report.UNKNOWN else Control.FAIL_NONRETRYABLE,
                      "EXECUTION_" + status.value, (self.execution.result_id,))
        self.inject("post_execution")
        self.observed = self.provider.observe(self.faults.observation_fault)
        self.journal.observed_version = self.observed.observation_version if self.observed else None
        self.reconciliation = reconcile(
            self.journal, self.envelope, self.before, self.baseline, self.execution,
            self.observed, self.journal.aggregate.authority_version)
        self.journal.event("TransitionReconciled" if self.reconciliation.outcome == Outcome.RECONCILED_SUCCESS
                           else "ReconciliationFailed", (self.reconciliation.reconciliation_id,),
                           self.reconciliation.outcome.value, attempt=self.supervisor.current)
        self.projection = project(self)
        return self.finish_index(self.result("COMPLETED"))

    def finish_index(self, result):
        if self.commit:
            entry = self.index[self.commit.idempotency_key]
            self.index[self.commit.idempotency_key] = replace(entry, result=result)
        return result

    def lookup(self, key, request, binding=None):
        entry = self.index[key]
        if request != entry.request or binding is not None and binding != entry.binding:
            return RunResult("REFUSED_DUPLICATE", Control.FAIL_NONRETRYABLE, None, None, None, None)
        if entry.result is None:
            return RunResult("HISTORICAL_INCOMPLETE", Control.HOLD_AMBIGUOUS, self.commit, None, None, None)
        return replace(entry.result, disposition="HISTORICAL_RETRIEVAL")

    def run(self, request=Request(), key="key-1", binding=None):
        if key in self.index:
            return self.lookup(key, request, binding)
        if self.supervisor.attempts:
            return RunResult("NO_SCOPE_RESET", Control.FAIL_NONRETRYABLE, None, None, None, None)
        if not self.prepare(request):
            return self.result()
        return self.realize(key, request.mode)
