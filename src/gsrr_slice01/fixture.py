"""Trusted in-memory fixture. Handlers receive requests, never this provider."""
from dataclasses import dataclass, replace
from .contracts import (
    Definition, AuthorityEvidence, Action, ObservedState, AuthoritativeStateSnapshot,
    FixedInput, Report, Mode,
)
from .journal import Journal


@dataclass(frozen=True)
class ActionRequest:
    kind: str
    value: str
    object_id: str = "DOC-001"


@dataclass(frozen=True)
class FixtureFaults:
    injections: tuple[tuple[str, str], ...] = ()
    candidate_count: int = 1
    selection_unknown: bool = False
    missing_intent: bool = False
    missing_profile: bool = False
    initial_read_missing: bool = False
    plan_defects: tuple[str, ...] = ()
    actions: tuple[ActionRequest, ...] | None = None
    allow_invalid_writes: bool = False
    reported_status: Report = Report.SUCCESS
    provider_raises: bool = False
    observation_fault: str = ""
    publication_fault: str = ""
    retention_unavailable: bool = False
    commit_retention_failure: bool = False
    failure_evidence_missing: bool = False
    scheduling_failure: bool = False
    payload_substitution: str = ""
    delegated_planning_failure: bool = False


@dataclass(frozen=True)
class EffectView:
    state: str = "DRAFT"
    exists: bool = True
    digest: str = "fixture-content-digest"
    version: int = 1
    predecessor: int | None = None
    commit_id: str | None = None


class Provider:
    def __init__(self, journal: Journal):
        self.journal = journal
        self.view = EffectView()
        self.actions: tuple[Action, ...] = ()
        self.read_count = 0
        self.invocation_count = 0
        self.current_invocation: str | None = None
        self.closed = False
        self.interval_start = 0

    def open_interval(self, commit_id: str) -> None:
        if self.current_invocation is not None:
            raise ValueError("single invocation already claimed")
        self.current_invocation = commit_id
        self.interval_start = len(self.actions)
        self.invocation_count += 1
        self.closed = False

    def apply(self, request: ActionRequest, fixed: FixedInput,
              diagnostic_invalid_write: bool = False) -> Action:
        if self.current_invocation is None or self.closed:
            raise ValueError("no active admitted invocation")
        before = self.view
        allowed = (
            request.object_id == fixed.object_id == "DOC-001"
            and request.kind == "STATE" and request.value == fixed.target_state == "REVIEW"
            and before.state == fixed.source_state == "DRAFT"
            and before.version == fixed.expected_observation_version
        )
        writable = request.kind in ("STATE", "CONTENT_WRITE", "EXISTS")
        apply_invalid = diagnostic_invalid_write and writable and request.object_id == "DOC-001"
        applied = allowed or apply_invalid
        after = before
        if applied:
            after = replace(
                before,
                state=request.value if request.kind == "STATE" else before.state,
                digest=request.value if request.kind == "CONTENT_WRITE" else before.digest,
                exists=request.value == "true" if request.kind == "EXISTS" else before.exists,
                version=before.version + 1, predecessor=before.version,
                commit_id=self.current_invocation,
            )
        entry = Action(
            len(self.actions) + 1, self.current_invocation, request.object_id,
            request.kind, request.value, applied,
            before.state, after.state, before.exists, after.exists,
            before.digest, after.digest, before.version, after.version,
            None if allowed else "FORBIDDEN_REQUEST",
        )
        # The complete request/outcome entry is retained before changing the effect view.
        self.actions += (entry,)
        self.journal.retain(f"{self.current_invocation}:action:{entry.sequence}", entry)
        self.view = after
        return entry

    def close_interval(self) -> str:
        self.closed = True
        ref = f"{self.current_invocation}:interval"
        self.journal.retain(ref, self.actions[self.interval_start:])
        return ref

    def observe(self, fault: str = "", initial: bool = False) -> ObservedState | None:
        self.read_count += 1
        if fault == "missing":
            return None
        v = self.view
        ref = self.journal.new_id("observation")
        actions = None if initial else self.actions[self.interval_start:]
        complete = None if initial else fault not in ("incomplete", "dropped")
        if fault == "dropped":
            actions = ()
        interval_ref = None if initial else f"{self.current_invocation}:interval"
        obs = ObservedState(
            ref, "STATE_PROVIDER", "DOC-001", v.state, v.exists, v.digest, v.version,
            v.predecessor, v.commit_id, self.read_count, interval_ref,
            None if initial else self.interval_start,
            None if initial else len(self.actions),
            None if initial else self.closed and fault != "unclosed",
            complete, "fixture-boundary", actions, fault == "conflicting",
        )
        if fault == "conflicting":
            alternate = replace(
                obs, snapshot_id=self.journal.new_id("conflicting-observation"),
                state="DRAFT" if obs.state == "REVIEW" else "REVIEW", conflicting=False,
            )
            self.journal.retain(alternate.snapshot_id, alternate)
            obs = replace(obs, conflicting_snapshot_ref=alternate.snapshot_id)
        self.journal.retain(ref, obs)
        return obs

    def snapshot(self, definition: Definition, observed: ObservedState):
        self.read_count += 1
        state = self.journal.aggregate
        record = AuthoritativeStateSnapshot(
            **self.journal.common("STATE_PROVIDER"),
            snapshot_id=self.journal.new_id("authority"), provider_id="STATE_PROVIDER",
            object_id="DOC-001", state=state.authority_state,
            authority_version=state.authority_version,
            observed_baseline_ref=observed.snapshot_id, exists=True,
            content_digest="fixture-content-digest",
            definition_ref=definition.definition_id, read_sequence=self.read_count,
        )
        return self.journal.retain(record.snapshot_id, record)

    def external_change(self, kind: str) -> None:
        """Trusted named stale-state injection; never passed to a handler."""
        if kind == "authority":
            self.journal.aggregate = replace(
                self.journal.aggregate, authority_state="REVIEW",
                authority_version=self.journal.aggregate.authority_version + 1,
            )
        elif kind == "observation":
            self.view = replace(self.view, version=self.view.version + 1,
                                state="REVIEW", commit_id="unrelated-writer")
        elif kind == "content":
            self.view = replace(self.view, digest="different",
                                version=self.view.version + 1, commit_id="unrelated-writer")


class RequestPort:
    """Data-only bounded request collector with no provider/store reference."""
    def __init__(self):
        self._requests: tuple[ActionRequest, ...] = ()

    def request(self, action: ActionRequest) -> None:
        self._requests += (action,)

    @property
    def requests(self) -> tuple[ActionRequest, ...]:
        return self._requests


class Capability:
    def __init__(self):
        self.explicit_calls = 0
        self.internal_planning_calls = 0

    def explicit(self, operation: FixedInput, port: RequestPort) -> None:
        self.explicit_calls += 1
        port.request(ActionRequest("STATE", operation.target_state, operation.object_id))

    def delegated(self, responsibility: FixedInput, port: RequestPort) -> None:
        self.internal_planning_calls += 1
        # Provider-owned pure derivation; there is no call to the GSRR planner.
        procedure = self.derive_procedure(responsibility)
        for request in procedure:
            port.request(request)

    @staticmethod
    def derive_procedure(responsibility: FixedInput) -> tuple[ActionRequest, ...]:
        return (ActionRequest("STATE", responsibility.target_state, responsibility.object_id),)

    def invoke(self, mode: Mode, fixed: FixedInput, port: RequestPort,
               faults: FixtureFaults) -> Report:
        if faults.delegated_planning_failure and mode == Mode.DELEGATED_REALIZATION:
            self.internal_planning_calls += 1
            raise ValueError("delegated pure planning failed")
        if faults.actions is None:
            if mode == Mode.EXPLICIT_PLAN:
                self.explicit(fixed, port)
            else:
                self.delegated(fixed, port)
        else:
            for request in faults.actions:
                port.request(request)
        if faults.provider_raises:
            raise ValueError("fixture provider exception after requested effects")
        return faults.reported_status
