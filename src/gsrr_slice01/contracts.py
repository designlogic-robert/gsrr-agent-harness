"""Immutable local Slice 01 contracts. Tuple fields serialize as DS lists."""
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum


class Mode(StrEnum):
    EXPLICIT_PLAN = "EXPLICIT_PLAN"
    DELEGATED_REALIZATION = "DELEGATED_REALIZATION"


class Gate(StrEnum):
    PASS = "PASS"
    REFUSED = "REFUSED"
    HELD = "HELD"


class Control(StrEnum):
    PASS = "PASS"
    REJECT_RETRYABLE = "REJECT_RETRYABLE"
    FAIL_NONRETRYABLE = "FAIL_NONRETRYABLE"
    HOLD_AMBIGUOUS = "HOLD_AMBIGUOUS"
    HUMAN_AUTHORIZATION_REQUIRED = "HUMAN_AUTHORIZATION_REQUIRED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


class Report(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


class Outcome(StrEnum):
    RECONCILED_SUCCESS = "RECONCILED_SUCCESS"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    STALE_STATE = "STALE_STATE"
    RECONCILIATION_AMBIGUOUS = "RECONCILIATION_AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class Decision(StrEnum):
    PROJECT = "PROJECT"
    DO_NOT_PROJECT = "DO_NOT_PROJECT"
    HOLD_PROJECTION = "HOLD_PROJECTION"


@dataclass(frozen=True)
class Check:
    criterion_ref: str
    observed_input_refs: tuple[str, ...]
    result: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class Artifact:
    run_id: str
    correlation_id: str
    producer: str
    artifact_version: str = "v0_1"

    @property
    def artifact_type(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class Definition:
    definition_id: str = "domain.document-review.fixture.v0_1"
    definition_version: int = 1
    object_id: str = "DOC-001"
    source_state: str = "DRAFT"
    target_state: str = "REVIEW"
    capability_id: str = "SUBMIT_FOR_REVIEW"
    implementation_id: str = "fixture.submit_for_review.v0_1"
    required_effects: tuple[str, ...] = ("REVIEW_ONCE",)
    forbidden_effects: tuple[str, ...] = (
        "CONTENT_WRITE", "DELETE", "APPROVED", "PUBLISHED", "OTHER_OBJECT",
        "DEFINITION_WRITE", "NESTED_DISPATCH", "NETWORK", "REPEAT_INVOCATION",
    )
    postconditions: tuple[str, ...] = (
        "EXISTS", "REVIEW", "UNCHANGED_CONTENT", "EXACT_IDENTITY",
        "OWN_SINGLE_INCREMENT", "COMPLETE_CLOSED_INTERVAL",
    )
    evidence_rules: tuple[str, ...] = (
        "INDEPENDENT_READ", "ALL_ACTIONS", "CLOSED_INTERVAL", "OWN_LINEAGE",
    )
    constraints: tuple[str, ...] = (
        "ONE_OBJECT", "ONE_INVOCATION", "NO_POST_ADMISSION_RETRY",
    )


@dataclass(frozen=True)
class AuthorityEvidence:
    evidence_id: str = "grant-1"
    issuer_id: str = "fixture-issuer"
    actor_id: str = "USER-001"
    object_id: str = "DOC-001"
    capability: str = "SUBMIT_FOR_REVIEW"
    implementation_id: str = "fixture.submit_for_review.v0_1"
    definition_version: int = 1
    source_authority_version: int = 1
    active: bool | None = True
    scope: str = "DOC-001:DRAFT:REVIEW"
    human_required: bool = False
    subject_ref: str | None = None
    policy_ref: str | None = None
    decision: str | None = None
    human_issuer: str | None = None


@dataclass(frozen=True)
class RetryPolicy:
    policy_id: str = "retry-1"
    policy_version: int = 1
    retry_enabled: bool = False
    allowed_failure_classes: tuple[str, ...] = ("GENERATED_PLAN_ENVELOPE_VIOLATION",)
    max_attempts: int = 1
    repeated_failure_threshold_or_null: int | None = None

    def valid(self) -> bool:
        threshold = self.repeated_failure_threshold_or_null
        return (
            type(self.policy_version) is int and self.policy_version >= 0
            and type(self.retry_enabled) is bool
            and type(self.allowed_failure_classes) is tuple
            and all(type(value) is str for value in self.allowed_failure_classes)
            and type(self.max_attempts) is int and self.max_attempts >= 1
            and (threshold is None or type(threshold) is int and threshold >= 1)
            and bool(self.policy_id)
        )


@dataclass(frozen=True)
class FixedInput:
    object_id: str
    source_state: str
    target_state: str
    expected_observation_version: int


@dataclass(frozen=True)
class Step:
    capability_id: str
    implementation_id: str
    fixed_input: FixedInput


@dataclass(frozen=True)
class DispatchPayload:
    object_id: str
    source_state: str
    target_state: str
    expected_observation_version: int
    capability_id: str
    implementation_id: str
    plan_id: str
    envelope_id: str
    commit_id: str
    idempotency_key: str
    invocation_id: str


@dataclass(frozen=True)
class Action:
    sequence: int
    invocation_id: str
    object_id: str
    action_kind: str
    requested_value: str
    applied: bool
    before_state: str
    after_state: str
    before_exists: bool
    after_exists: bool
    before_digest: str
    after_digest: str
    before_version: int
    after_version: int
    reason: str | None


@dataclass(frozen=True)
class ObservedState:
    snapshot_id: str
    provider_id: str
    object_id: str
    state: str
    exists: bool
    content_digest: str
    observation_version: int
    predecessor_version: int | None
    commit_id: str | None
    read_sequence: int
    action_log_ref: str | None
    interval_start: int | None
    interval_end: int | None
    interval_closed: bool | None
    complete_for_invocation: bool | None
    fixture_boundary_ref: str
    actions: tuple[Action, ...] | None
    conflicting: bool = False
    conflicting_snapshot_ref: str | None = None


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    attempt_number: int
    prior_attempt_id: str | None
    terminal: bool = False
    failure_class: str | None = None


@dataclass(frozen=True)
class ScopeLedger:
    scope_ref: str
    policy_ref: str
    attempts_created: int
    active_attempt_id: str | None
    scheduled_attempt_id: str | None = None
    admission_seen: bool | None = False
    circuit_state: str = "CLOSED"
    scheduling_known: bool = True


@dataclass(frozen=True)
class ControlPayload:
    kind: str
    original_artifact_refs: tuple[str, ...]
    failure_class_or_null: str | None
    violated_rule_refs: tuple[str, ...]
    reasons: tuple[str, ...]
    gate_disposition_or_null: Gate | None
    supervisory_disposition_or_null: Control | None
    terminal_attempt: bool
    scope_ref: str | None
    policy_ref: str | None
    attempts_created_before: int | None
    attempts_created_after: int | None
    max_attempts: int | None
    circuit_state: str
    current_state_check_refs: tuple[str, ...]
    authority_check_refs: tuple[str, ...]
    approval_ref: str | None
    envelope_ref: str | None
    no_effect_check_refs: tuple[str, ...]
    admission_seen: bool | None
    dispatch_or_effect_posture: str
    scheduled_attempt_id_or_null: str | None
    escalation_kind_or_null: str | None


@dataclass(frozen=True)
class StructuredIntent(Artifact):
    intent_id: str
    actor_id: str
    object_type: str
    object_id: str
    objective: str
    requested_target_state: str
    unresolved_fields: tuple[str, ...]
    sufficiency_policy_ref: str


@dataclass(frozen=True)
class AuthoritativeStateSnapshot(Artifact):
    snapshot_id: str
    provider_id: str
    object_id: str
    state: str
    authority_version: int
    observed_baseline_ref: str
    exists: bool
    content_digest: str
    definition_ref: str
    read_sequence: int


@dataclass(frozen=True)
class CandidateTransition(Artifact):
    transition_id: str
    intent_id: str
    snapshot_id: str
    object_id: str
    source_state: str
    source_authority_version: int
    source_observation_version: int
    target_state: str
    definition_ref: str
    rationale: str
    unresolved_fields: tuple[str, ...]


@dataclass(frozen=True)
class CandidateSelection(Artifact):
    selection_id: str
    considered_transition_ids: tuple[str, ...]
    selected_transition_id_or_null: str | None
    selection_policy_ref: str
    environment_ref: str
    selection_eligible: bool | None
    disposition: str
    reasons: tuple[str, ...]
    unresolved_fields: tuple[str, ...]
    sufficiency_policy_ref: str


@dataclass(frozen=True)
class TransitionValidationResult(Artifact):
    validation_id: str
    transition_id: str
    snapshot_id: str
    definition_ref: str
    checked_authority_version: int
    checked_observation_version: int
    check_results: tuple[Check, ...]
    disposition: Gate
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ApprovedTransition(Artifact):
    approval_id: str
    transition_id: str
    validation_id: str
    object_id: str
    source_authority_version: int
    source_observation_version: int
    target_state: str
    actor_id: str
    authority_evidence_refs: tuple[str, ...]
    definition_ref: str
    authority_check_results: tuple[Check, ...]
    disposition: Gate


@dataclass(frozen=True)
class ExecutionEnvelope(Artifact):
    envelope_id: str
    approval_id: str
    transition_id: str
    object_id: str
    source_state: str
    target_state: str
    source_authority_version: int
    source_observation_version: int
    definition_ref: str
    authority_evidence_refs: tuple[str, ...]
    required_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    required_capability: str
    allowed_implementation_ids: tuple[str, ...]
    postconditions: tuple[str, ...]
    reconciliation_requirements: tuple[str, ...]
    execution_constraints: tuple[str, ...]
    envelope_check_results: tuple[Check, ...]
    fixture_boundary_ref: str


@dataclass(frozen=True)
class ExecutionPlan(Artifact):
    plan_id: str
    envelope_id: str
    transition_id: str
    object_id: str
    source_authority_version: int
    source_observation_version: int
    steps: tuple[Step, ...]
    accepted_envelope_obligations_ref: str
    sufficiency_policy_ref: str
    unresolved_fields: tuple[str, ...]
    attempt_id: str
    realization_mode: Mode


@dataclass(frozen=True)
class PlanValidationResult(Artifact):
    plan_validation_id: str
    plan_id: str
    envelope_id: str
    approval_id: str
    checked_authority_version: int
    checked_observation_version: int
    authority_evidence_refs: tuple[str, ...]
    check_results: tuple[Check, ...]
    disposition: Gate
    reasons: tuple[str, ...]
    attempt_id: str


@dataclass(frozen=True)
class RealizationCommit(Artifact):
    commit_id: str
    transition_id: str
    object_id: str
    source_state_version: int
    source_observation_version: int
    target_state: str
    execution_envelope_id: str
    execution_plan_id: str
    plan_validation_id: str
    authority_evidence_refs: tuple[str, ...]
    idempotency_key: str
    required_postconditions: tuple[str, ...]
    reconciliation_obligation: tuple[str, ...]
    status: str
    event_ref: str
    definition_ref: str
    actor_id: str
    capability_id: str
    implementation_id: str
    dispatch_payload: DispatchPayload
    attempt_id: str


@dataclass(frozen=True)
class CapabilityDescriptor(Artifact):
    descriptor_id: str
    capability_id: str
    implementation_id: str
    descriptor_version: int
    input_contract_ref: str
    expected_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    authority_requirements: str
    idempotency_posture: str
    fixture_boundary_ref: str
    action_observation_contract_ref: str
    supported_realization_modes: tuple[Mode, ...]
    owns_internal_planning_by_mode: tuple[tuple[Mode, bool], ...]
    supports_reconciliation_evidence: bool


@dataclass(frozen=True)
class ExecutionResult(Artifact):
    result_id: str
    commit_id: str
    plan_id: str
    capability_id: str
    implementation_id: str
    object_id: str
    expected_observation_version: int
    dispatch_started: bool
    reported_status: Report
    error_or_null: str | None
    idempotency_key: str
    event_ref: str
    invocation_id: str
    dispatched_payload_ref: str
    action_interval_ref: str | None


@dataclass(frozen=True)
class ReconciliationResult(Artifact):
    reconciliation_id: str
    commit_id: str
    approval_id: str
    result_id: str
    before_snapshot_id: str
    observed_snapshot_ref: str | None
    object_id: str
    authority_version_checked: int | None
    observed_version: int | None
    observed_predecessor_version: int | None
    observed_commit_id: str | None
    checks: tuple[Check, ...]
    required_effect_findings: tuple[str, ...]
    forbidden_effect_findings: tuple[str, ...]
    postcondition_findings: tuple[str, ...]
    outcome: Outcome
    unresolved_fields: tuple[str, ...]
    sufficiency_policy_ref: str
    action_interval_ref: str | None
    fixture_boundary_ref: str
    completeness_findings: tuple[str, ...]
    invocation_binding_checks: tuple[Check, ...]


@dataclass(frozen=True)
class ProjectionDecision(Artifact):
    projection_id: str
    transition_id: str
    reconciliation_id: str
    commit_id: str
    object_id: str
    plan_ref: str
    envelope_ref: str
    definition_ref: str
    initial_and_current_snapshot_refs: tuple[str, ...]
    expected_authority_version: int
    current_authority_version_or_null: int | None
    reconciled_observation_version: int | None
    current_observation_version_or_null: int | None
    action_interval_ref: str | None
    target_state: str
    authority_evidence_refs: tuple[str, ...]
    checks: tuple[Check, ...]
    final_decision: Decision
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    write_outcome: str
    authoritative_state_changed: bool
    projected_authority_version_or_null: int | None
    retention_ref: str
    journal_record_status: str


@dataclass(frozen=True)
class RuntimeEvent(Artifact):
    event_id: str
    event_type: str
    sequence: int
    causation_id_or_null: str | None
    actor_or_component: str
    object_id: str
    transition_id_or_null: str | None
    commit_id_or_null: str | None
    source_authority_version_or_null: int | None
    observed_version_or_null: int | None
    artifact_refs: tuple[str, ...]
    outcome: str
    reason_codes: tuple[str, ...]
    visibility: str
    attempt_id_or_null: str | None
    parent_transition_id_or_null: str | None
    attempt_number_or_null: int | None
    prior_attempt_id_or_null: str | None
    retry_policy_ref_or_null: str | None
    control_payload_or_null: ControlPayload | None


def plain(value):
    """JSON evidence conversion only; runtime dispatch does not use reflection."""
    if is_dataclass(value):
        result = {f.name: plain(getattr(value, f.name)) for f in fields(value)}
        if isinstance(value, CapabilityDescriptor):
            result["owns_internal_planning_by_mode"] = dict(value.owns_internal_planning_by_mode)
        if isinstance(value, Artifact):
            result["artifact_type"] = value.artifact_type
        return result
    if isinstance(value, tuple):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value
