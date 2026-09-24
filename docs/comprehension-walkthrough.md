# GSRR Slice 01 — Execution-First Comprehension Walkthrough

Version: v0_1  
Status: PUBLIC_COMPREHENSION_SUPPORT  
Scope: GSRR Operation Core Slice 01  
Production status: NOT_PRODUCTION

## Purpose

This walkthrough is designed to understand Slice 01 by following one execution from input to authoritative result.

It deliberately starts with:

```text
What command enters?
Where is it stored?
What function receives it?
What can mutate?
What is observed?
What test proves the behavior?
```

rather than beginning with the full architecture vocabulary.

The existence of this document does **not** establish human comprehension. The comprehension gate is satisfied only when the reviewer can explain the relevant flow and boundaries independently.

---

## 1. Start by running the two visible behaviors

From the repository root:

```bash
python examples/success_path.py
python examples/false_success_path.py
```

The success path should end approximately as:

```text
Execution report      : SUCCESS
Observed state        : REVIEW
Reconciliation        : RECONCILED_SUCCESS
Projection decision   : PROJECT / APPLIED
Authoritative state   : DRAFT -> REVIEW
```

The false-success path should end approximately as:

```text
Execution report      : SUCCESS
Observed state        : DRAFT
Reconciliation        : RECONCILIATION_FAILED
Projection decision   : DO_NOT_PROJECT / NOT_ATTEMPTED
Authoritative state   : DRAFT -> DRAFT
```

If those two cases make sense, you already have the core problem:

```text
tool success is not enough
```

The rest of the runtime explains what must happen between a request and authoritative acceptance.

---

## 2. The input object

Open:

```text
src/gsrr_slice01/runtime.py
```

Find:

```python
@dataclass(frozen=True)
class Request:
    request_id: str = "request-1"
    actor_id: str = "USER-001"
    object_id: str = "DOC-001"
    target_state: str = "REVIEW"
    mode: Mode = Mode.EXPLICIT_PLAN
```

For the normal fixture, the request means:

```text
USER-001
requests
DOC-001
to move to
REVIEW
```

Notice what it does **not** mean:

```text
DOC-001 is now REVIEW
```

It is only an input request.

---

## 3. The top-level entry point

In `runtime.py`, find:

```python
SliceRuntime.run()
```

Its normal path is conceptually:

```text
run()
  ↓
prepare()
  ↓
realize()
```

Before preparation, `run()` also checks whether the same idempotency key already has retained history.

So the first major question is:

> Is this a new request scope, or a historical request that should be retrieved rather than executed again?

---

## 4. What exists when `SliceRuntime()` is created

Construction creates the bounded runtime environment:

```text
Journal
Definition
AuthorityEvidence
Provider
Capability
Planner
Supervisor
```

The two state views begin separately:

```text
provider observed state = DRAFT
journal authoritative state = DRAFT
```

They happen to agree initially.

They are still different responsibilities.

A useful mental model is:

```text
Provider
= what the execution environment currently shows

Journal aggregate authority
= what the governed runtime currently accepts as authoritative
```

---

## 5. `prepare()` — form and govern the requested WHAT

`prepare()` is the front half of the operation.

### 5.1 Structured intent

The request becomes `StructuredIntent`.

The runtime retains it in the journal and emits:

```text
IntentStructured
```

If required identity/profile information is missing, execution stops here.

### 5.2 Read the baseline

The runtime asks the provider for the initial observed state.

Then it forms an authoritative snapshot that binds the initial:

```text
object
state
content digest
authority version
observation version
definition
```

This gives the future transition a concrete source state.

### 5.3 Candidate transition

The runtime creates:

```text
CandidateTransition
DRAFT -> REVIEW
```

This is still only a candidate.

Remember:

```text
CandidateTransition(REVIEW)
!=
authoritative REVIEW
```

### 5.4 Candidate selection

The fixture selects the one eligible candidate and records `CandidateSelection`.

Selection answers:

> Which candidate are we considering?

It does **not** answer:

> Is the transition valid?

or:

> Is the actor authorized?

### 5.5 Transition validation

The runtime checks the bounded fixture edge and preconditions.

Normal case:

```text
USER-001
DOC-001
DRAFT -> REVIEW
```

passes.

Trying:

```text
DRAFT -> APPROVED
```

does not.

### 5.6 Authorization

After validation, the runtime separately checks supplied authority evidence.

This is one of the important boundaries:

```text
valid transition
!=
authorized transition
```

Only after the authority check passes is an `ApprovedTransition` retained.

### 5.7 Execution envelope

The runtime then creates the `ExecutionEnvelope`.

Think of the envelope as the ceiling around realization:

```text
this target
this object
this authority
these required effects
these forbidden effects
this capability
these allowed implementations
these postconditions
these evidence obligations
```

At this point the approved WHAT is bounded.

Nothing has been executed yet.

---

## 6. `realize()` — choose and validate HOW

`realize()` handles the realization path.

For the normal example:

```text
Mode.EXPLICIT_PLAN
```

the planner creates one bounded `ExecutionPlan`.

The plan is then independently checked by `validate_plan()`.

The separation is:

```text
planner proposes HOW
        ↓
validator checks HOW against approved WHAT
```

If the plan broadens the target, effects, implementation, or required obligations, the plan does not receive execution admission.

If eligible retry behavior is involved, a failed attempt becomes terminal and a separate successor must satisfy fresh checks.

The same failed attempt is never silently reopened.

---

## 7. Freshness check before commit

Before creating a realization commit, the runtime calls its freshness logic.

It compares current material against the original approved basis.

Questions include:

```text
Is authority still the expected version?
Is observed state still the expected state?
Is the definition unchanged?
Is the approved transition unchanged?
Is the envelope unchanged?
Is the grant still valid?
```

If those facts are no longer established, the runtime does not continue as though the original approval were still fresh.

---

## 8. `admit()` — create a RealizationCommit

`admit()` creates a `RealizationCommit`.

This is a critical vocabulary point:

```text
RealizationCommit
!=
authoritative state commit
```

It means the runtime has accepted responsibility to attempt the bounded realization.

It binds:

```text
transition
envelope
plan
plan validation
authority evidence
idempotency key
capability
implementation
exact dispatch payload
attempt identity
```

The document is still authoritatively `DRAFT`.

---

## 9. `dispatch()` — cross the effect boundary

Before invoking the capability, `dispatch()` checks that the presented payload still exactly matches the retained approved/validated material.

Then it:

```text
claims the idempotency key
opens an action interval
invokes the capability
collects requested actions through RequestPort
applies those actions through the Provider
closes the action interval
creates ExecutionResult
```

The capability does not receive unrestricted authority to mutate arbitrary runtime state.

Inside this fixture, requested effects are mediated through the bounded provider interface.

The execution result records what the executor/provider reports:

```text
SUCCESS
FAILURE
UNKNOWN
```

That report is evidence.

It is not authoritative state.

---

## 10. Independent observation after execution

After execution, the runtime reads the provider again:

```python
self.observed = self.provider.observe(...)
```

This is where the system asks:

> What state do we now actually observe?

For a normal successful realization:

```text
observed = REVIEW
```

For the false-success fixture:

```text
ExecutionResult = SUCCESS
observed = DRAFT
```

That is why the architecture needs a step after execution.

---

## 11. `reconcile()` — compare the claim with the evidence

Open:

```text
src/gsrr_slice01/reconciliation.py
```

Find:

```python
reconcile(...)
```

Reconciliation checks evidence such as:

```text
complete action interval
forbidden actions
current authority
attribution
target postconditions
exact invocation lineage
```

Its active outcomes are:

```text
RECONCILED_SUCCESS
RECONCILIATION_FAILED
STALE_STATE
RECONCILIATION_AMBIGUOUS
UNRESOLVED
```

### Normal success

The required effect exists, the action history is complete and compliant, and the state is attributable to the expected invocation:

```text
RECONCILED_SUCCESS
```

### False success

The provider reported `SUCCESS`, but the complete independent evidence still shows the unchanged baseline:

```text
DRAFT
```

That is a known required-effect mismatch:

```text
RECONCILIATION_FAILED
```

The system does not reinterpret the provider's `SUCCESS` as stronger evidence than its independent reconciliation.

---

## 12. `project()` — decide whether authority may change

After reconciliation, the runtime calls:

```python
project(runtime)
```

This is the final authority gate.

The possible final decisions are:

```text
PROJECT
DO_NOT_PROJECT
HOLD_PROJECTION
```

### Failed reconciliation

```text
RECONCILIATION_FAILED
→ DO_NOT_PROJECT
```

No authoritative state update is attempted.

### Ambiguous, stale, or unresolved reconciliation

```text
STALE_STATE
RECONCILIATION_AMBIGUOUS
UNRESOLVED
→ HOLD_PROJECTION
```

### Reconciled success

Even `RECONCILED_SUCCESS` does not immediately change authority.

The runtime performs fresh final checks first.

Only then can it produce:

```text
PROJECT / APPLIED
```

and publish:

```text
authoritative state:
DRAFT -> REVIEW
```

So:

```text
reconciliation success
!=
authority
```

---

## 13. Where authoritative state actually changes

Open:

```text
src/gsrr_slice01/journal.py
```

Find:

```python
Journal.publish(...)
```

The aggregate authority changes only when publication is called with a new authoritative state.

Conceptually:

```text
ProjectionDecision = PROJECT
        ↓
Journal.publish(..., new_state="REVIEW")
        ↓
authority_state = REVIEW
authority_version += 1
```

Negative decisions publish retained evidence without changing the authoritative state.

This is the final answer to:

> What code actually makes REVIEW authoritative?

Not the request.

Not candidate selection.

Not validation.

Not authorization.

Not the plan.

Not commit.

Not provider `SUCCESS`.

Not even reconciliation alone.

The authority change occurs through the final successful projection publication.

---

## 14. Follow the canonical success test

Open:

```text
tests/gsrr_slice01/test_runtime.py
```

Find:

```python
test_s01_t01_success
```

Read it as an executable story.

It verifies, among other things:

```text
control = PASS
reconciliation = RECONCILED_SUCCESS
projection = PROJECT
write outcome = APPLIED
provider invocation count = 1
observed provider state = REVIEW
authoritative state = REVIEW
authority version = 2
```

It also checks ordering across the main runtime events.

This is the shortest test-level proof of the successful full chain.

---

## 15. Follow the canonical false-success test

In the same file, find:

```python
test_s01_t05_false_native_success
```

The test intentionally supplies:

```python
FixtureFaults(actions=())
```

The provider still reports:

```text
SUCCESS
```

but the required REVIEW effect never occurred.

The test verifies:

```text
ExecutionResult.reported_status
= SUCCESS

ReconciliationResult.outcome
= RECONCILIATION_FAILED

ProjectionDecision.final_decision
= DO_NOT_PROJECT

authoritative state
= DRAFT
```

This is the smallest executable demonstration of the project's central thesis:

```text
provider success != realized authoritative state
```

---

## 16. Why final-state history matters

The fixture also records an action interval rather than checking only the final visible state.

Why?

Because this:

```text
DRAFT
→ APPROVED
→ REVIEW
```

and this:

```text
DRAFT
→ REVIEW
```

can end in the same visible final state while representing different execution histories.

The approved envelope permits only the bounded expected realization.

Therefore reconciliation needs both:

```text
current observed state
+
attributable action history
```

---

## 17. Why ambiguous effects block blind retry

If the system cannot establish whether an effect occurred, automatically repeating the command can duplicate or compound effects.

Slice 01 therefore distinguishes:

```text
known eligible pre-admission plan failure
```

from:

```text
admission occurred
dispatch occurred
effect occurred
effect may have occurred
effect status is unknown
```

Only the narrowly enabled pre-admission failure class can create an automatic successor, and only after fresh no-effect checks.

That is why:

```text
unknown != safe to retry
```

---

## 18. One-page mental model

If you remember only this, remember:

```text
Request
  ↓
Candidate
  ↓
Validate
  ↓
Authorize
  ↓
Envelope
  ↓
Plan
  ↓
Validate plan
  ↓
Commit realization responsibility
  ↓
Dispatch
  ↓
Tool reports
  ↓
Observe independently
  ↓
Reconcile
  ↓
Fresh final gate
  ↓
Project authority
```

And the three highest-value distinctions are:

```text
proposal != authority

provider success != realized authoritative state

reconciliation != projection
```

---

## 19. Human comprehension check

Before treating the comprehension gate as satisfied, the reviewer should be able to answer these without reading the answer text:

1. What is the difference between observed state and authoritative state?
2. What does `CandidateTransition` establish, and what does it not establish?
3. Why are validation and authorization separate?
4. What does the `ExecutionEnvelope` bound?
5. Why is `RealizationCommit` not the same as authoritative `REVIEW`?
6. What exactly does `ExecutionResult.SUCCESS` prove?
7. Why does the runtime observe after execution?
8. What causes the false-success case to become `RECONCILIATION_FAILED`?
9. Why does `RECONCILED_SUCCESS` still need a final projection gate?
10. Which operation actually changes authoritative state?
11. Why is a complete action interval stronger evidence than final-state equality alone?
12. Why can ambiguous or possible effects suppress automatic retry?

A satisfactory explanation does not need to reproduce class definitions from memory.

It should show that the reviewer understands the runtime boundaries and can trace the main execution path.

---

## 20. Practical interview-level explanation

A concise explanation of Slice 01 is:

> The runtime does not let a requested state or a tool's success response become authoritative directly. It separately validates and authorizes the transition, bounds realization through an execution envelope and validated plan, commits the realization attempt, executes through a mediated provider, independently observes the resulting state and action history, reconciles that evidence against what was approved, and only then passes a fresh final projection gate that may update authoritative state. The false-success test demonstrates the key failure case: the provider can report success while the required state change did not happen, and the runtime keeps the authoritative state unchanged.

If that explanation is understood rather than memorized, the main Slice 01 architecture is understood at the level this public walkthrough is intended to support.
