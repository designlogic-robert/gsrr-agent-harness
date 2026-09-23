# Slice 01 Contracts

Version: v0_1  
Status: BOUNDED_PUBLIC_PROJECTION  
Production Status: NOT_PRODUCTION

## Contract Boundary

These contracts define the public Slice 01 fixture and its executable control boundaries.

They are local Python-facing contracts for this bounded demonstration. They are not universal transport schemas and do not claim to reproduce the complete private architectures named by local responsibility labels.

## Fixture State and Authority

| Fixture field | Required value / invariant |
|---|---|
| Definition | `domain.document-review.fixture.v0_1`, immutable identity plus definition version |
| Entity / actor | `Document / DOC-001`; `USER-001` |
| Initial authoritative view | `DRAFT`, `authority_version=1` |
| Initial independently observed view | `DRAFT`, `observation_version=1`, object exists, nonempty content digest |
| Allowed edge | `DRAFT -> REVIEW` only |
| Capability / implementation | `SUBMIT_FOR_REVIEW / fixture.submit_for_review.v0_1` |
| Expected effect | one mediated `REVIEW` update with observation version 2 and predecessor version 1 |
| Required postconditions | same object exists; state is `REVIEW`; content unchanged; exact own invocation lineage; complete closed action interval |
| Prohibitions | content mutation/restore, deletion/recreation, direct `APPROVED`/`PUBLISHED`, other-object or definition writes, nested dispatch, network effects through the fixture interface, repeated invocation |
| Grant | trusted supplied evidence exactly scoped to actor, object, capability, implementation, definition and source authority version |
| Authoritative admission | only final `PROJECT / APPLIED` increments authority once to version 2 |

The provider maintains distinct logical views:

```text
observed state
!=
authoritative state
```

Capability execution can change the observed view through the mediator. Projection alone may change the authoritative view.

Equal numeric definition, observation and authority versions remain distinct namespaces.

## Common Types

Every top-level artifact carries:

```text
artifact_type
artifact_version
run_id
correlation_id
producer
```

References resolve to retained immutable records.

Important enums:

```text
Gate:
PASS | REFUSED | HELD

Execution report:
SUCCESS | FAILURE | UNKNOWN

Reconciliation:
RECONCILED_SUCCESS
RECONCILIATION_FAILED
STALE_STATE
RECONCILIATION_AMBIGUOUS
UNRESOLVED

Projection:
PROJECT
DO_NOT_PROJECT
HOLD_PROJECTION

Write outcome:
APPLIED
NOT_ATTEMPTED
FAILED

Realization mode:
EXPLICIT_PLAN
DELEGATED_REALIZATION
```

Unknown material is explicit. Missing evidence never defaults to permission or success.

## Typed Artifact Contracts

Slice 01 retains fifteen top-level artifact types.

### 1. StructuredIntent

Records the requested objective and material identity.

Principal fields:

```text
intent_id
actor_id
object_type
object_id
objective
requested_target_state
unresolved_fields
sufficiency_policy_ref
```

### 2. AuthoritativeStateSnapshot

Binds the provider-supported authoritative baseline.

Principal fields:

```text
snapshot_id
provider_id
object_id
state
authority_version
observed_baseline_ref
exists
content_digest
definition_ref
read_sequence
```

### 3. CandidateTransition

Proposes one future state without creating authority.

Principal fields:

```text
transition_id
intent_id
snapshot_id
object_id
source_state
source_authority_version
source_observation_version
target_state
definition_ref
rationale
unresolved_fields
```

### 4. CandidateSelection

Records candidate eligibility/selection only.

Principal fields:

```text
selection_id
considered_transition_ids
selected_transition_id_or_null
selection_policy_ref
environment_ref
selection_eligible
disposition
reasons
unresolved_fields
sufficiency_policy_ref
```

Selection does not validate or authorize the transition.

### 5. TransitionValidationResult

Records domain/state validity checks.

Principal fields:

```text
validation_id
transition_id
snapshot_id
definition_ref
checked_authority_version
checked_observation_version
check_results
disposition
reasons
```

### 6. ApprovedTransition

Binds the separate authorization result.

Principal fields:

```text
approval_id
transition_id
validation_id
object_id
source_authority_version
source_observation_version
target_state
actor_id
authority_evidence_refs
definition_ref
authority_check_results
disposition
```

Approval exists only on a passing authorization decision.

### 7. ExecutionEnvelope

Defines the immutable approved realization boundary.

Principal fields:

```text
envelope_id
approval_id
transition_id
object_id
source_state
target_state
source_authority_version
source_observation_version
definition_ref
authority_evidence_refs
required_effects
forbidden_effects
required_capability
allowed_implementation_ids
postconditions
reconciliation_requirements
execution_constraints
envelope_check_results
fixture_boundary_ref
```

The envelope is mode-neutral. It is not regenerated to accommodate a different HOW.

### 8. ExecutionPlan

Binds one realization step.

Principal fields:

```text
plan_id
envelope_id
transition_id
object_id
source_authority_version
source_observation_version
steps
accepted_envelope_obligations_ref
sufficiency_policy_ref
unresolved_fields
attempt_id
realization_mode
```

The single step contains only:

```text
capability_id
implementation_id
fixed_input:
  object_id
  source_state
  target_state
  expected_observation_version
```

Commit, idempotency-key and invocation metadata are excluded from `fixed_input`.

### 9. PlanValidationResult

Independently validates exact plan/envelope conformance.

Principal fields:

```text
plan_validation_id
plan_id
envelope_id
approval_id
checked_authority_version
checked_observation_version
authority_evidence_refs
check_results
disposition
reasons
attempt_id
```

### 10. RealizationCommit

Records acceptance of realization responsibility before effects.

Principal fields:

```text
commit_id
transition_id
object_id
source_state_version
source_observation_version
target_state
execution_envelope_id
execution_plan_id
plan_validation_id
authority_evidence_refs
idempotency_key
required_postconditions
reconciliation_obligation
status
event_ref
definition_ref
actor_id
capability_id
implementation_id
dispatch_payload
attempt_id
```

`RealizationCommit` is control state, not authoritative domain state.

The dispatch payload contains exactly the validated fixed input plus:

```text
capability_id
implementation_id
plan_id
envelope_id
commit_id
idempotency_key
invocation_id = commit_id
```

No late semantic, mode or attempt field may be injected.

### 11. CapabilityDescriptor

Describes the supplied implementation and fixture boundary.

Principal fields:

```text
descriptor_id
capability_id
implementation_id
descriptor_version
input_contract_ref
expected_effects
forbidden_effects
authority_requirements
idempotency_posture
fixture_boundary_ref
action_observation_contract_ref
supported_realization_modes
owns_internal_planning_by_mode
supports_reconciliation_evidence
```

For this fixture the same implementation supports both realization modes.

### 12. ExecutionResult

Records the executor/provider report, not observed truth.

Principal fields:

```text
result_id
commit_id
plan_id
capability_id
implementation_id
object_id
expected_observation_version
dispatch_started
reported_status
error_or_null
idempotency_key
event_ref
invocation_id
dispatched_payload_ref
action_interval_ref
```

`SUCCESS` is occurrence/report evidence only.

### 13. ReconciliationResult

Compares execution/report evidence with independently observed state and action history.

Principal fields:

```text
reconciliation_id
commit_id
approval_id
result_id
before_snapshot_id
observed_snapshot_ref
object_id
authority_version_checked
observed_version
observed_predecessor_version
observed_commit_id
checks
required_effect_findings
forbidden_effect_findings
postcondition_findings
outcome
unresolved_fields
sufficiency_policy_ref
action_interval_ref
fixture_boundary_ref
completeness_findings
invocation_binding_checks
```

### 14. ProjectionDecision

Records the retained final admission decision.

Principal fields:

```text
projection_id
transition_id
reconciliation_id
commit_id
object_id
plan_ref
envelope_ref
definition_ref
initial_and_current_snapshot_refs
expected_authority_version
current_authority_version_or_null
reconciled_observation_version
current_observation_version_or_null
action_interval_ref
target_state
authority_evidence_refs
checks
final_decision
reason_codes
reasons
write_outcome
authoritative_state_changed
projected_authority_version_or_null
retention_ref
journal_record_status
```

`authoritative_state_changed=true` is valid only for `PROJECT / APPLIED`.

### 15. RuntimeEvent

Preserves material causal history.

Principal fields include:

```text
event_id
event_type
sequence
causation_id_or_null
actor_or_component
object_id
transition_id_or_null
commit_id_or_null
artifact_refs
outcome
reason_codes
visibility
attempt_id_or_null
parent_transition_id_or_null
attempt_number_or_null
prior_attempt_id_or_null
retry_policy_ref_or_null
control_payload_or_null
```

Event occurrence does not create authority.

## Fixture Observation Boundary

All effect requests cross a trusted bounded mediator.

The mediator records requests before application and resulting writes before return. The action interval includes denied actions and retains:

```text
sequence
invocation_id
object_id
action_kind
requested value / bounded digest reference
applied
before / after state
before / after existence
before / after digest
before / after observation version
refusal / error reason
```

A final matching state alone is insufficient to prove compliant realization.

Examples:

```text
content mutate → restore
delete → recreate
APPROVED → REVIEW
PUBLISHED → REVIEW
```

remain violations even if the final snapshot resembles the required result.

Missing, dropped, unclosed or inconsistent action history never proves absence.

## Realization Modes

### EXPLICIT_PLAN

```text
approved WHAT
→ planner creates one-step HOW
→ independent plan validation
→ commit
→ execution
```

### DELEGATED_REALIZATION

```text
approved WHAT
→ coordinator binds bounded capability responsibility
→ independent plan validation of that boundary instruction
→ commit
→ provider derives internal pure procedure
→ all effects still cross the mediator
```

The same approval and envelope apply to both modes.

```text
mode change != permission change
```

## Execution Admission and Dispatch

Required lineage:

```text
ExecutionEnvelope
→ ExecutionPlan
→ PlanValidationResult
→ RealizationCommit
→ dispatch claim
→ ExecutionResult
```

Before commit and again before dispatch, fresh state/version/grant checks must still match the original immutable basis.

The exact run-local dispatch key is claimed once before invocation.

Unknown prior dispatch, missing records or stale material prevent invocation.

## Reconciliation Precedence

All findings are retained. Primary classification follows this order:

1. known forbidden applied action, denied forbidden request or known execution failure → `RECONCILIATION_FAILED`;
2. otherwise changed current authority or unrelated writer/version/commit lineage → `STALE_STATE`;
3. otherwise conflicting provider observations or unknown execution attribution → `RECONCILIATION_AMBIGUOUS`;
4. otherwise missing required read, interval completeness or predicate → `UNRESOLVED`;
5. otherwise fully evidenced attributable mismatch → `RECONCILIATION_FAILED`;
6. otherwise complete matching lineage and all required predicates → `RECONCILED_SUCCESS`.

A provider `SUCCESS` report with independently observed unchanged `DRAFT` is a known missing effect and therefore fails reconciliation.

## Execution, Reconciliation and Projection

| Reconciliation / final check | Final decision | Authority |
|---|---|---|
| `RECONCILIATION_FAILED` / known forbidden result | `DO_NOT_PROJECT / NOT_ATTEMPTED` | unchanged |
| `STALE_STATE`, `RECONCILIATION_AMBIGUOUS`, `UNRESOLVED` | `HOLD_PROJECTION / NOT_ATTEMPTED` | preserve current authority |
| `RECONCILED_SUCCESS`, final grant known invalid | `DO_NOT_PROJECT / NOT_ATTEMPTED` | unchanged |
| `RECONCILED_SUCCESS`, final read/version/history token missing or mismatched | `HOLD_PROJECTION / NOT_ATTEMPTED` | unchanged |
| `RECONCILED_SUCCESS`, all fresh checks pass and publication succeeds | `PROJECT / APPLIED` | increment once to `REVIEW` |
| publication/preparation failure | `DO_NOT_PROJECT / FAILED` | unchanged |

Successful reconciliation does not itself alter authoritative state.

## Human / Supervisory Dispositions

The runtime keeps supervisory disposition separate from gate, execution, reconciliation and projection enums:

```text
PASS
REJECT_RETRYABLE
FAIL_NONRETRYABLE
HOLD_AMBIGUOUS
HUMAN_AUTHORIZATION_REQUIRED
CIRCUIT_OPEN
```

Key distinctions:

- known invalid ordinary authority → nonretryable failure;
- unknown/conflicting material → hold;
- explicitly human-reserved missing authorization → human authorization required;
- circuit exhaustion → human investigation;
- AI participation alone does not create a human-approval requirement.

## Bounded Retry / Successor Contract

Every non-success attempt is terminal.

Automatic creation of a distinct successor is allowed only for the explicitly enabled:

```text
GENERATED_PLAN_ENVELOPE_VIOLATION
```

and only before any realization admission or possible effect.

The retry scope is bound to:

```text
run_id
parent_transition_id
approval_id
envelope_id
```

Before successor allocation, the runtime must freshly revalidate:

```text
source identity and versions
definition
target
grant / authority
approval subject
unchanged envelope
retained terminal failure evidence
no admission
no dispatch
no effect / possible effect
remaining finite budget
closed circuit
```

Any commit/admission, dispatch, actual effect, possible effect or unknown effect forbids automatic regeneration.

`max_attempts` counts the initial attempt and every successor. Exhaustion or the configured repeated-failure threshold opens the scope circuit and requires retained human investigation.

## Idempotent Historical Retrieval

The run-local idempotency key is checked before fresh execution reads.

- exact retained tuple → return historical records without redispatch or reprojection;
- same key with changed tuple → refuse;
- incomplete/unknown retained attempt → return held/incomplete state without inventing retry or result.

## Non-Claims

These contracts do not establish:

```text
production authentication
production IAM / revocation
arbitrary-host security
general sandboxing
distributed durability
distributed transactions
restart recovery
concurrency safety
arbitrary provider trust
```

They specify only the deterministic closed Slice 01 fixture.
