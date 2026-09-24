# GSRR State Realization Skill

Status: PUBLIC_BOUNDED_PROCEDURE  
Applies to: `gsrr-agent-harness` Slice 01 state-realization work  
Production status: NOT_PRODUCTION

## When to use this procedure

Use this Skill when a task can change or materially interpret any of the following:

```text
transition selection
transition validation
authorization
ExecutionEnvelope
ExecutionPlan
plan validation
RealizationCommit
dispatch
provider effects
observation
reconciliation
projection
retry / successor behavior
idempotency / historical retrieval
authoritative state
```

Pure spelling, formatting, or non-semantic prose edits do not require the full procedure unless they alter a public claim.

## Objective

Make the smallest justified change while preserving the tested separation:

```text
requested
!= authorized
!= executed
!= observed
!= reconciled
!= authoritative
```

## Procedure

### 1. Bind the task

State the requested outcome in one sentence.

Classify it as:

```text
DOCUMENTATION_ONLY
TEST_ONLY
IMPLEMENTATION_PRESERVING
NORMATIVE_BEHAVIOR_CHANGE
UNCLEAR
```

If `UNCLEAR`, inspect before editing.

### 2. Identify normative impact

Read:

```text
specification/slice-01/requirements.yaml
specification/slice-01/acceptance-scenarios.yaml
specification/slice-01/contracts.md
```

Identify affected requirement IDs and scenarios.

Do not infer that a requirement changes merely because implementation structure changes.

### 3. Inspect the executable path

Use only the modules relevant to the task:

```text
contracts.py
fixture.py
governance.py
journal.py
reconciliation.py
retry.py
runtime.py
```

For runtime flow, begin with:

```text
SliceRuntime.run()
→ prepare()
→ realize()
→ admit()
→ dispatch()
→ reconcile()
→ project()
```

Do not read unrelated surfaces merely to increase context.

### 4. Inspect proof obligations

Locate the tests that challenge the affected behavior.

Key anchors include:

```text
test_s01_t01_success
test_s01_t02_invalid_what
test_s01_t03_insufficient_authority
test_s01_t04_plan_and_delegated_bounds
test_s01_t05_false_native_success
test_s01_t06_freshness_seams
test_s01_t07_*
test_s01_t08_same_what_distinct_how
```

Preserve negative-path evidence.

A failing negative test may indicate that the proposed implementation weakened a control boundary.

### 5. Form a bounded change

Before mutation, preserve these questions:

```text
What may change?
What must not change?
Which authoritative assumption is relied upon?
Which effect is permitted?
Which effect is forbidden?
What evidence must exist afterward?
What should happen if evidence is missing or conflicting?
```

If the proposed change enlarges scope beyond the current fixture, stop and report the scope expansion.

### 6. Preserve critical invariants

Do not collapse:

```text
CandidateTransition -> authority
CandidateSelection -> validation
TransitionValidationResult -> authorization
ApprovedTransition -> execution admission
ExecutionResult.SUCCESS -> realized state
ReconciliationResult -> authoritative projection
```

Do not use final-state equality as sufficient evidence when the action interval is incomplete or contains a forbidden action.

Do not convert:

```text
UNKNOWN
AMBIGUOUS
MISSING
POSSIBLE_EFFECT
```

into implicit success or implicit no-effect evidence.

### 7. Verify locally

Run targeted tests for the affected behavior when useful.

Then run:

```bash
python -m pytest -q
```

Current expected baseline:

```text
148 passed
```

If the task changes an example-facing behavior, also run:

```bash
python examples/success_path.py
python examples/false_success_path.py
```

### 8. Reconcile documentation

If normative behavior changed, reconcile:

```text
specification
implementation
tests
docs
examples
```

If behavior did not change, do not rewrite the specification merely to match implementation wording.

### 9. Report the result

Return a compact completion report:

```text
Task classification:
Requirements affected:
Files changed:
Behavior:
Targeted verification:
Full-suite verification:
Scope expansion:
Remaining uncertainty:
```

## Stop conditions

Stop rather than guessing when:

- public specification and implementation materially conflict;
- required authority or source material is unavailable;
- a task requires a private source that is not present;
- the requested change would silently expand the Slice 01 domain;
- correct behavior under ambiguous/possible-effect state cannot be established;
- passing the task appears to require weakening a normative negative test;
- publication, release, architecture acceptance, or production status would have to be self-declared.

## Non-claims

Successful use of this Skill demonstrates a structured agent procedure.

It does not prove:

```text
instruction non-bypassability
hard capability enforcement
secure sandboxing
production governance
general agent reliability
```
