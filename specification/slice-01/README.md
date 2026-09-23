# GSRR Operation Core — Slice 01

Version: v0_1  
Status: BOUNDED_PUBLIC_PROJECTION  
Implementation: IMPLEMENTED_AND_TESTED_IN_CLOSED_FIXTURE  
Production Status: NOT_PRODUCTION

## Purpose

Slice 01 is a bounded executable demonstration of governed state realization.

It governs one proposed `Document` transition, realizes an approved target through a bounded capability, independently observes what actually happened, reconciles the result against the approved transition and evidence obligations, and admits the new authoritative state only through a retained final projection decision.

The protected fixture transition is:

```text
DOC-001
DRAFT
  ↓
REVIEW
```

The central problem is that these states are not interchangeable:

```text
proposal
!= selection
!= validation
!= authorization
!= execution admission
!= execution report
!= observed result
!= reconciled result
!= authoritative projection
```

A tool or provider reporting `SUCCESS` is therefore not sufficient to establish that the intended state was realized.

## Scope

The public Slice 01 fixture is deliberately small:

```text
single process
single synchronous run
single document
single allowed state edge
single registered implementation
trusted in-memory provider
append-only in-memory journal
deterministic planning / test doubles
no network required
```

The fixture exists to make the control boundaries testable, not to claim production completeness.

## Fixture

| Surface | Bounded value |
|---|---|
| Object | `Document / DOC-001` |
| Actor | `USER-001` |
| Initial authoritative state | `DRAFT`, authority version 1 |
| Initial observed state | `DRAFT`, observation version 1 |
| Allowed edge | `DRAFT -> REVIEW` only |
| Capability | `SUBMIT_FOR_REVIEW` |
| Implementation | `fixture.submit_for_review.v0_1` |
| Expected effect | one mediated `REVIEW` update |
| Required result | object still exists, content unchanged, exact invocation lineage, complete closed action interval |
| Authoritative admission | only `PROJECT / APPLIED` advances authority to `REVIEW` |

## Runtime Model

The governed path is:

```text
request
  ↓
idempotency / prior-result check
  ↓
initial authoritative + observed state
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
single bounded dispatch
  ↓
ExecutionResult
  ↓
independent observation
  ↓
ReconciliationResult
  ↓
ProjectionDecision
  ↓
authoritative state update only on PROJECT / APPLIED
```

Pre-dispatch failure does not fabricate a projection decision. Once execution has occurred, the runtime independently observes and reconciles before authority can advance.

## Approved WHAT vs Realization HOW

The approved **WHAT** is bound by the immutable transition, approval and execution envelope.

Slice 01 supports two bounded realization modes:

```text
EXPLICIT_PLAN
→ the planner supplies the one-step HOW

DELEGATED_REALIZATION
→ the coordinator binds the same approved capability responsibility
→ the provider derives its internal pure procedure
```

Both modes remain subject to the same approved target, authority, effects, constraints, evidence obligations, reconciliation and final projection gate.

Changing HOW does not enlarge WHAT.

## Core Invariants

```text
discoverable != permitted != applicable != selected != authorized

proposal != authority

selection != validation

validation != authorization

authorization != execution admission

plan != execution authority

provider success != realized authoritative state

execution != reconciliation

reconciliation != projection
```

Additional rules:

- the authoritative state remains `DRAFT` through execution and reconciliation;
- provider effects change the observed view, not authoritative state directly;
- only a retained `PROJECT / APPLIED` decision can advance authority to `REVIEW`;
- failed, stale, ambiguous and unresolved reconciliation cannot project;
- every completed projection evaluation retains one final decision;
- a failed attempt is terminal and cannot resume;
- bounded automatic successor creation is limited to the explicitly enabled pre-admission generated-plan failure class;
- any admission, dispatch, possible effect, actual effect or unknown effect blocks automatic regeneration.

## Reconciliation Outcomes

Active reconciliation outcomes are:

```text
RECONCILED_SUCCESS
RECONCILIATION_FAILED
STALE_STATE
RECONCILIATION_AMBIGUOUS
UNRESOLVED
```

`PARTIAL_REALIZATION` is not an active Slice 01 outcome.

Successful reconciliation establishes **eligibility for final admission**, not authority by itself.

## Public Responsibility Labels

The implementation and specification retain labels such as `PCPK`, `DASA`, and `MSP` where they identify the bounded responsibility represented in Slice 01.

Those labels do **not** mean this public repository contains the complete private PCPK, DASA, or MSP architectures. In this repository they identify only the local responsibility exercised by the Slice fixture.

## Specification Files

```text
specification/slice-01/
├── README.md
├── requirements.yaml
├── acceptance-scenarios.yaml
├── contracts.md
└── topology/
    ├── operation-flow.mmd
    └── authority-and-evidence.mmd
```

`requirements.yaml` carries the 27 Slice requirements.

`acceptance-scenarios.yaml` carries the eight base acceptance scenarios and six diagnostic case groups used to define the expected behavioral boundary.

`contracts.md` defines the fixture state, typed artifacts, realization modes, reconciliation precedence, projection decisions and bounded retry controls.

The Mermaid files provide the operation and authority/evidence topology.

## Executable Relationship

The public implementation lives under:

```text
src/gsrr_slice01/
```

and its executable verification lives under:

```text
tests/gsrr_slice01/
```

The specification defines the bounded behavior the implementation is intended to realize. Passing tests support the tested fixture behavior; they do not establish production readiness, universal correctness or applicability outside the declared boundary.

## Non-Goals

Slice 01 does not establish:

- production identity or IAM;
- arbitrary-host sandboxing;
- distributed execution or distributed transactions;
- crash/restart durability;
- concurrency correctness;
- natural-language intent correctness;
- live model correctness;
- arbitrary external-provider trust;
- generic legal or commercial workflow correctness;
- universal GSRR production readiness.

It is a deliberately closed proof case for governed state realization.
