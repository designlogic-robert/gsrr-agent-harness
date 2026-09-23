"""Run-local immutable record history and one aggregate publication boundary."""
from dataclasses import dataclass, replace
from .contracts import Artifact, RuntimeEvent, ProjectionDecision


@dataclass(frozen=True)
class RunAggregate:
    authority_state: str = "DRAFT"
    authority_version: int = 1
    records: tuple[tuple[str, object], ...] = ()
    events: tuple[RuntimeEvent, ...] = ()
    outcome_slots: tuple[tuple[str, ProjectionDecision | None], ...] = ()


class RetentionError(RuntimeError):
    pass


class Journal:
    def __init__(self, run_id: str = "run-1"):
        self.run_id = run_id
        self.aggregate = RunAggregate()
        self._serial = 0
        self.transition_ref = None
        self.commit_ref = None
        self.source_version = None
        self.observed_version = None

    def new_id(self, kind: str) -> str:
        self._serial += 1
        return f"{self.run_id}:{kind}:{self._serial}"

    def common(self, producer: str) -> dict:
        return dict(run_id=self.run_id, correlation_id=self.run_id, producer=producer)

    def get(self, ref: str):
        for key, record in self.aggregate.records:
            if key == ref:
                return record
        raise KeyError(ref)

    def retain(self, ref: str, record):
        if not ref:
            raise RetentionError("empty reference")
        try:
            old = self.get(ref)
        except KeyError:
            old = None
        if old is not None:
            if old != record:
                raise RetentionError("immutable reference replacement")
            return record
        self.aggregate = replace(
            self.aggregate, records=self.aggregate.records + ((ref, record),)
        )
        return record

    def event(self, event_type: str, refs: tuple[str, ...] = (), outcome: str = "PASS",
              reason: str = "", attempt=None, transition=None, commit=None,
              source_version=None, observed_version=None, policy=None, payload=None,
              event_id: str | None = None) -> RuntimeEvent:
        for ref in refs:
            self.get(ref)
        events = self.aggregate.events
        transition = self.transition_ref if transition is None else transition
        commit = self.commit_ref if commit is None else commit
        source_version = self.source_version if source_version is None else source_version
        observed_version = self.observed_version if observed_version is None else observed_version
        event = RuntimeEvent(
            **self.common("EVENT_JOURNAL"), event_id=event_id or self.new_id("event"),
            event_type=event_type, sequence=len(events) + 1,
            causation_id_or_null=events[-1].event_id if events else None,
            actor_or_component="GSRR_SLICE_01", object_id="DOC-001",
            transition_id_or_null=transition, commit_id_or_null=commit,
            source_authority_version_or_null=source_version,
            observed_version_or_null=observed_version, artifact_refs=refs,
            outcome=outcome, reason_codes=(reason,) if reason else (),
            visibility="INTERNAL_BOUNDED_TRACE",
            attempt_id_or_null=attempt.attempt_id if attempt else None,
            parent_transition_id_or_null=transition,
            attempt_number_or_null=attempt.attempt_number if attempt else None,
            prior_attempt_id_or_null=attempt.prior_attempt_id if attempt else None,
            retry_policy_ref_or_null=policy, control_payload_or_null=payload,
        )
        self.retain(event.event_id, event)
        self.aggregate = replace(self.aggregate, events=events + (event,))
        return event

    def reserve(self, ref: str, inputs: tuple[str, ...], fail: bool = False) -> bool:
        if fail:
            return False
        self.retain(ref, inputs)
        self.aggregate = replace(
            self.aggregate, outcome_slots=self.aggregate.outcome_slots + ((ref, None),)
        )
        return True

    def publish(self, decision: ProjectionDecision, event: RuntimeEvent | None,
                new_state: str | None = None) -> None:
        """One assignment publishes authority, decision and event together."""
        old = self.aggregate
        if not any(k == decision.retention_ref and v is None for k, v in old.outcome_slots):
            raise RetentionError("missing or already completed outcome slot")
        if any(k == decision.projection_id for k, _ in old.records):
            raise RetentionError("duplicate final evaluation")
        records = old.records + ((decision.projection_id, decision),)
        events = old.events
        if event is not None:
            records += ((event.event_id, event),)
            events += (event,)
        slots = tuple((k, decision if k == decision.retention_ref else v)
                      for k, v in old.outcome_slots)
        candidate = RunAggregate(
            authority_state=new_state if new_state is not None else old.authority_state,
            authority_version=old.authority_version + (1 if new_state is not None else 0),
            records=records, events=events, outcome_slots=slots,
        )
        self.aggregate = candidate

    def artifact_types(self) -> tuple[str, ...]:
        return tuple(r.artifact_type for _, r in self.aggregate.records
                     if isinstance(r, Artifact))
