# Architecture

Version: v0_1  
Status: BOUNDED_PUBLIC_EXPLANATION  
Scope: GSRR Operation Core Slice 01  
Production status: NOT_PRODUCTION

## 1. Architectural objective

Slice 01 governs and realizes one proposed document-state transition while preventing an unverified result from becoming authoritative.

The fixture protects:

```text
DOC-001
DRAFT -> REVIEW
```

The target state may become authoritative only after the runtime has preserved and checked the distinctions among proposal, validation, authorization, execution, observation, reconciliation, and projection.

The core invariant is:

```text
requested state
!= approved state change
!= executed action
!= observed result
!= reconciled result
!= authoritative state
```

## 2. System boundary

Slice 01 is intentionally closed:

```text
one process
one synchronous run
one document
one allowed transition
one registered implementation
trusted in-memory provider
append-only in-memory journal
deterministic planner/test behavior
no network dependency
```

The architecture is therefore a bounded executable specimen, not a production deployment architecture.

## 3. State boundary

The provider maintains two logical views:

```text
observed state
!=
authoritative state
```

At the beginning:

```text
authoritative:
DOC-001 = DRAFT
authority_version = 1

observed:
DOC-001 = DRAFT
observation_version = 1
```

A capability invocation may change the **observed** view through the mediated fixture.

It does not directly change authoritative state.

Only the final projection operation may advance authoritative state:

```text
PROJECT / APPLIED
        ↓
authoritative DOC-001 = REVIEW
authority_version = 2
```

This separation is what makes it possible for the runtime to observe a tool effect without immediately treating that effect as accepted system truth.

## 4. Runtime path

The high-level path is:

```text
Request
  ↓
historical/idempotency lookup
  ↓
authoritative + observed baseline
  ↓
StructuredIntent
  ↓
CandidateTransition
  ↓
CandidateSelection
  ↓
TransitionValidationResult
  ↓
ApprovedTransition
  ↓
ExecutionEnvelope
  ↓
ExecutionPlan
  ↓
PlanValidationResult
  ↓
RealizationCommit
  ↓
dispatch claim
  ↓
ExecutionResult
  ↓
independent observation
  ↓
ReconciliationResult
  ↓
ProjectionDecision
  ↓
authoritative update only if PROJECT / APPLIED
```

The public Mermaid version is in
[`../specification/slice-01/topology/operation-flow.mmd`](../specification/slice-01/topology/operation-flow.mmd).

## 5. Responsibility separations

### Proposal is not authority

`CandidateTransition` describes a possible future state. It does not authorize or realize that state.

```text
CandidateTransition(REVIEW)
!=
authoritative REVIEW
```

### Selection is not validation

`CandidateSelection` identifies the candidate being considered.

It does not establish that the transition is valid.

### Validation is not authorization

The transition can be structurally valid while the actor lacks sufficient scoped authority.

The runtime therefore treats:

```text
allowed transition
```

and:

```text
permission to perform that transition
```

as different questions.

### Authorization is not execution admission

An approved transition still requires a bounded realization envelope, a plan, independent plan validation, fresh checks, and a retained commit before dispatch.

### Commit is not domain-state authority

`RealizationCommit` records accepted realization responsibility before effects.

It changes GSRR control state.

It does not change the document's authoritative state to `REVIEW`.

### Execution report is not observed truth

`ExecutionResult.reported_status` can be:

```text
SUCCESS
FAILURE
UNKNOWN
```

A `SUCCESS` report is retained as execution evidence, but independent observation and reconciliation determine what the run can establish about actual realization.

### Reconciliation is not projection

`RECONCILED_SUCCESS` means the evidence is sufficient to reach the final projection gate.

It does not itself mutate authority.

## 6. Approved WHAT vs realization HOW

Slice 01 preserves an immutable approved **WHAT** while allowing two bounded forms of **HOW**.

### EXPLICIT_PLAN

```text
approved WHAT
  ↓
external planner creates one-step HOW
  ↓
independent plan validation
  ↓
commit
  ↓
execution
```

### DELEGATED_REALIZATION

```text
approved WHAT
  ↓
coordinator binds the approved capability responsibility
  ↓
independent validation of the bounded instruction
  ↓
commit
  ↓
provider derives its internal pure procedure
  ↓
execution
```

Both modes remain constrained by the same:

```text
target
authority
envelope
required effects
forbidden effects
postconditions
evidence obligations
reconciliation
projection gate
```

Therefore:

```text
mode change != permission change
```

and:

```text
HOW may vary
without enlarging WHAT
```

## 7. Execution envelope

The `ExecutionEnvelope` is the realization ceiling.

It binds:

```text
approved target
source versions
authority evidence
required effects
forbidden effects
required capability
allowed implementation
postconditions
reconciliation requirements
execution constraints
fixture boundary
```

The planner may choose a valid HOW inside that envelope.

The planner may not broaden it.

A plan that adds content mutation, changes the target, changes the implementation outside the allowed set, or omits required evidence obligations is refused or held before dispatch.

## 8. Commit and dispatch

Before invocation, the runtime retains a `RealizationCommit` and an exact dispatch payload.

The payload binds the validated fixed input to:

```text
capability_id
implementation_id
plan_id
envelope_id
commit_id
idempotency_key
invocation_id
```

Fresh permission/version checks and exact equality checks occur before dispatch.

This protects against a validated plan being replaced or materially mutated after validation.

## 9. Mediated effects

All fixture effect requests pass through a bounded mediator.

The action history records, among other things:

```text
sequence
invocation identity
object identity
action kind
requested value
applied / denied status
before and after state
before and after existence
before and after digest
before and after observation version
reason
```

The complete closed interval matters because final state alone can hide invalid intermediate behavior.

For example:

```text
content mutate
→ content restore
→ final REVIEW
```

does not satisfy the fixture merely because the final content appears unchanged.

Likewise:

```text
APPROVED
→ REVIEW
```

or:

```text
delete
→ recreate
→ REVIEW
```

remains a violation when the action history attributes those effects to the invocation.

## 10. Reconciliation

Reconciliation compares the approved transition and execution evidence against independent provider evidence.

The five active outcomes are:

```text
RECONCILED_SUCCESS
RECONCILIATION_FAILED
STALE_STATE
RECONCILIATION_AMBIGUOUS
UNRESOLVED
```

Primary classification preserves precedence:

```text
known forbidden / denied-forbidden / known failed execution
    ↓
STALE_STATE
    ↓
RECONCILIATION_AMBIGUOUS
    ↓
UNRESOLVED
    ↓
fully evidenced attributable mismatch
    ↓
RECONCILED_SUCCESS
```

All material findings are retained even when one outcome becomes primary.

### False success

A central test case is:

```text
execution report = SUCCESS
observed state = unchanged DRAFT
action interval = complete
```

Because the required effect is known not to have occurred, the result is:

```text
RECONCILIATION_FAILED
→ DO_NOT_PROJECT
→ authoritative state remains DRAFT
```

## 11. Projection

A completed final projection evaluation retains exactly one decision:

```text
PROJECT
DO_NOT_PROJECT
HOLD_PROJECTION
```

Only:

```text
PROJECT / APPLIED
```

may advance authority.

Typical mapping:

```text
RECONCILIATION_FAILED
→ DO_NOT_PROJECT

STALE_STATE
RECONCILIATION_AMBIGUOUS
UNRESOLVED
→ HOLD_PROJECTION

RECONCILED_SUCCESS
→ fresh final checks
→ PROJECT only if those checks still pass
```

A grant may become invalid or state may change after reconciliation. That is why the final gate remains distinct.

## 12. Bounded retry and successor creation

A failed attempt is terminal.

The runtime does not reopen the same failed attempt.

A distinct automatic successor may be created only for the explicitly enabled pre-admission generated-plan envelope-violation class and only when fresh checks establish that no admission, dispatch, effect, possible effect, or unknown effect occurred.

Conceptually:

```text
failed attempt
    ↓
terminal evidence retained
    ↓
eligible failure class?
    ↓
fresh state / authority / envelope / budget checks
    ↓
no possible effect?
    ↓
new distinct attempt OR stop/escalate
```

Ambiguous or possible effects therefore suppress blind retry.

## 13. Module map

The public implementation is intentionally small.

| Module | Primary responsibility |
|---|---|
| `contracts.py` | enums, immutable typed artifacts, fixture definition and serialization helpers |
| `fixture.py` | trusted in-memory provider, mediated actions, capability behavior and observation |
| `governance.py` | authority checks, envelope construction, plan construction/instruction and plan validation |
| `journal.py` | immutable record retention, runtime events, key reservation and projection publication |
| `reconciliation.py` | post-execution reconciliation and final projection evaluation |
| `retry.py` | terminal attempt supervision, successor eligibility, finite budget and circuit behavior |
| `runtime.py` | orchestration of request, preparation, realization, admission, dispatch, observation and result return |
| `__init__.py` | package identity |

The typed contracts and exact field-level requirements are documented in
[`../specification/slice-01/contracts.md`](../specification/slice-01/contracts.md).

## 14. Public responsibility labels

The implementation retains local producer/responsibility labels such as:

```text
PCPK
DASA
MSP
```

Inside this public repository those labels identify bounded Slice 01 responsibilities.

They do not claim that this repository publishes the complete architectures associated with those names.

## 15. Architectural claim boundary

The architecture demonstrates that these separations can be made explicit and executable inside the deterministic fixture.

It does not establish that the same mechanisms are sufficient for:

```text
production IAM
distributed systems
arbitrary external providers
untrusted host execution
concurrent mutation
crash/restart recovery
live-model correctness
```

See [`limitations.md`](limitations.md).
