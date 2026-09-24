# Design Evolution

Version: v0_1  
Status: BOUNDED_PUBLIC_EXPLANATION  
Scope: GSRR Operation Core Slice 01 design rationale

## Purpose

This document explains the design questions that produced the major Slice 01 separations.

It is not a chronological transcript of the private development process.

The useful unit here is:

```text
initial concern
→ failure scenario
→ architectural question
→ distinction
→ requirement
→ executable representation
```

The goal is to show why the architecture contains its current boundaries rather than presenting the final code as self-explanatory.

---

## 1. A proposed future state must not become authoritative merely because it was proposed

### Initial concern

An AI system can propose a plausible future state.

That proposal may be useful without being authoritative.

### Failure scenario

```text
model proposes:
DOC-001 -> REVIEW

system treats proposal as current truth
```

The system would have collapsed:

```text
candidate state
=
authoritative state
```

before validation, authority, execution, or verification occurred.

### Architectural question

What does a proposal actually establish?

### Distinction

```text
proposal != authority
```

A `CandidateTransition` is an explicit future-state candidate tied to intent, object identity, source state/version, target state, and definition.

It remains non-authoritative.

### Resulting requirements

Public Slice requirements make this explicit:

```text
S01-R01
Bound typed proposals to explicit intent, object, definition and version;
never infer authority.

S01-R03
Use supplied candidate selection while preserving non-selection
without granting authority.
```

### Slice representation

```text
StructuredIntent
    ↓
CandidateTransition
    ↓
CandidateSelection
```

None of those artifacts changes authoritative `DOC-001` from `DRAFT`.

---

## 2. A valid transition and permission to perform it are different questions

### Initial concern

`DRAFT -> REVIEW` may be a valid domain transition while a particular actor lacks sufficient authority to perform it.

### Failure scenario

```text
transition is structurally valid
        ↓
system assumes permission
        ↓
execution begins without valid scoped authority
```

### Architectural question

Should transition validity imply authorization?

### Distinction

```text
validation != authorization
```

### Resulting requirements

```text
S01-R04
Check the fixture allowed edge and every precondition before authorization.

S01-R05
Consume scoped external fixture authority evidence;
refuse missing/inactive/wrong issuer or scope.
```

### Slice representation

```text
TransitionValidationResult
        ↓
separate authority evaluation
        ↓
ApprovedTransition
```

A valid target can still be refused because authorization is insufficient.

Unknown authority can be held rather than silently converted into permission.

---

## 3. Authorization should bind WHAT without allowing realization HOW to broaden it

### Initial concern

Once a transition is approved, the mechanism that realizes it still has implementation choices.

If the planner or provider can reinterpret the approved goal, authorization becomes porous.

### Failure scenario

The approved target is:

```text
DOC-001:
DRAFT -> REVIEW
```

but a generated plan also:

```text
mutates content
targets APPROVED
uses an unapproved implementation
or drops evidence obligations
```

### Architectural question

How can the system permit implementation choice without allowing implementation choice to redefine the approved transition?

### Distinction

```text
approved WHAT
!=
realization HOW
```

and:

```text
HOW may vary
without enlarging WHAT
```

### Resulting requirements

```text
S01-R06
Build and validate a complete execution envelope.

S01-R07
Create one immutable fixed-input step.

S01-R08
Independently validate exact plan/envelope conformance.

S01-R26
Bind explicit or delegated realization as immutable HOW
under the same mode-neutral approval/envelope.
```

### Slice representation

```text
ApprovedTransition
        ↓
ExecutionEnvelope
        ↓
EXPLICIT_PLAN
or
DELEGATED_REALIZATION
        ↓
PlanValidationResult
```

Both realization modes are required to preserve the same target, authority, effects, constraints and evidence obligations.

---

## 4. A successful tool call must not be mistaken for successful realization

### Initial concern

External tools and adapters report their own execution status.

A native `SUCCESS` report does not necessarily prove that the intended resulting state exists.

### Failure scenario

```text
requested:
DRAFT -> REVIEW

provider report:
SUCCESS

independent observation:
DRAFT
```

### Architectural question

What has actually been established by the tool's success flag?

### Distinction

```text
provider success
!=
realized authoritative state
```

### Resulting requirements

```text
S01-R12
Treat execution report as occurrence evidence,
including failure and uncertainty.

S01-R13
Reconcile required effects using independent state
and complete mediated action history.

S01-R15
Only fresh complete success can advance authority.
```

### Slice representation

```text
ExecutionResult(SUCCESS)
        ↓
independent observation
        ↓
ReconciliationResult(RECONCILIATION_FAILED)
        ↓
ProjectionDecision(DO_NOT_PROJECT)
        ↓
authoritative state remains DRAFT
```

This is the project's canonical false-success demonstration.

---

## 5. Final state alone is not enough to prove compliant execution

### Initial concern

A workflow can end in the expected visible state after taking prohibited intermediate actions.

If the runtime checks only the final state, it can miss those violations.

### Failure scenarios

```text
content mutate
→ content restore
→ REVIEW
```

```text
delete
→ recreate
→ REVIEW
```

```text
APPROVED
→ REVIEW
```

All three can end with a final snapshot that appears superficially acceptable.

### Architectural question

Is a matching final state sufficient evidence of compliant realization?

### Distinction

```text
final snapshot
!=
complete realization history
```

### Resulting requirements

```text
S01-R06
Bind forbidden-action evidence obligations into the envelope.

S01-R13
Use independent state and complete provider-mediated action history.
```

### Slice representation

The fixture mediator retains a closed action interval containing applied and denied requests, identities, before/after state, content digest and observation versions.

Reconciliation evaluates the complete attributable interval rather than merely comparing:

```text
final_state == REVIEW
```

This allows a matching final state to still fail reconciliation when the route to that state violated the approved envelope.

---

## 6. Reconciliation success should create eligibility, not immediate authority

### Initial concern

Even after execution evidence reconciles successfully, the conditions that allowed the transition may have changed before authority is written.

### Failure scenario

```text
execution reconciles successfully
        ↓
grant becomes invalid
or current version changes
        ↓
system projects REVIEW anyway
```

### Architectural question

Should successful reconciliation itself mutate authoritative state?

### Distinction

```text
reconciliation != projection
```

and:

```text
RECONCILED_SUCCESS
=
eligible for final gate
```

not:

```text
RECONCILED_SUCCESS
=
authoritative target
```

### Resulting requirements

```text
S01-R15
Every completed final projection evaluation retains one final decision;
only fresh complete success can advance authority.

S01-R16
Publish authority update and retained decision as one local fixture operation.
```

### Slice representation

```text
ReconciliationResult(RECONCILED_SUCCESS)
        ↓
fresh final state / authority checks
        ↓
ProjectionDecision
        ↓
PROJECT / APPLIED
or
DO_NOT_PROJECT / HOLD_PROJECTION
```

Negative final decisions preserve the current authoritative state.

---

## 7. Ambiguous execution should suppress blind retry

### Initial concern

After a timeout, missing acknowledgment, uncertain dispatch, or possible effect, the system may not know whether an operation happened.

Blindly retrying can duplicate or compound effects.

### Failure scenario

```text
dispatch outcome = unknown
        ↓
agent assumes failure
        ↓
same operation is invoked again
```

### Architectural question

When is automatic retry safe?

### Distinction

```text
known pre-admission plan failure
!=
possible post-dispatch effect
```

and:

```text
COMPLETE NO-EFFECT EVIDENCE
is required before the bounded successor path
```

### Resulting requirements

```text
S01-R21
Every non-success attempt is terminal.
Admission, dispatch, effect, possible effect or unknown effect
forbids automatic regeneration.

S01-R22 through S01-R25
Permit only a narrowly enabled pre-admission successor path
with fresh checks, finite budget, retained lineage and escalation.
```

### Slice representation

```text
attempt fails
    ↓
attempt becomes terminal
    ↓
eligible failure class?
    ↓
fresh checks + no-effect evidence?
    ↓
budget/circuit available?
    ↓
new distinct attempt
or
stop / human investigation
```

The architecture therefore treats uncertainty as a reason to constrain progression rather than as permission to repeat an effect.

---

## 8. Resulting architecture pattern

The accumulated distinctions produce the Slice 01 control chain:

```text
proposal
  ↓
selection
  ↓
validation
  ↓
authorization
  ↓
bounded realization
  ↓
execution
  ↓
independent observation
  ↓
reconciliation
  ↓
fresh final gate
  ↓
authoritative projection
```

The architecture is intentionally more explicit than a direct:

```text
request
→ tool call
→ success
```

because the intermediate distinctions are where the system preserves scope, authority, evidence and uncertainty.

## 9. What this evolution does not claim

These design choices are supported only inside the declared Slice 01 fixture.

The project does not claim that they are the only possible architecture for governed state realization, that every production system needs every artifact, or that the current fixture proves production correctness.

The purpose of Slice 01 is narrower:

> Make the distinctions explicit enough to implement, test, challenge, and revise.
