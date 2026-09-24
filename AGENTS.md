# Agent Operating Instructions

Repository: `gsrr-agent-harness`  
Scope: public GSRR Operation Core Slice 01  
Status: public operating contract  
Production status: NOT_PRODUCTION

## Purpose

This repository is a bounded, runnable case study of governed state realization.

Agent-assisted work must preserve the distinction between:

```text
proposal
!= validation
!= authorization
!= execution
!= observation
!= reconciliation
!= authoritative projection
```

The repository's current public proof is intentionally narrow. Do not broaden it silently.

## Source order

For work affecting Slice 01 behavior, use this precedence:

```text
1. explicit current task
2. specification/slice-01/
3. tests/gsrr_slice01/
4. src/gsrr_slice01/
5. docs/ and examples/
```

If these surfaces conflict materially, stop and report the conflict rather than inventing a new rule.

## Core invariants

Preserve:

```text
proposal != authority
selection != validation
validation != authorization
authorization != execution admission
plan != execution authority
provider success != realized authoritative state
execution != reconciliation
reconciliation != projection
observed state != authoritative state
```

Only a retained `PROJECT / APPLIED` projection may advance authoritative state in the current fixture.

## Scope discipline

The v0.1 fixture is limited to:

```text
DOC-001
DRAFT -> REVIEW
single synchronous process
trusted in-memory provider
single registered capability implementation
deterministic closed fixture
```

Do not silently add production IAM, networking, distributed execution, new domains, arbitrary state transitions, additional providers, or generalized security claims.

## Before changing behavior

For any change to `src/gsrr_slice01/` or behavioral tests:

1. identify the affected requirement IDs in `specification/slice-01/requirements.yaml`;
2. identify the relevant acceptance or diagnostic scenarios;
3. inspect the corresponding contracts and tests;
4. state whether the change preserves, clarifies, or changes normative behavior.

If normative behavior changes, update the public specification and tests in the same bounded change.

## Mutation rules

- Prefer the smallest change sufficient for the explicit task.
- Preserve immutable-reference and state/authority boundaries.
- Do not weaken a negative test merely to obtain a green suite.
- Do not convert unknown or ambiguous material into permission, success, or no-effect proof.
- Do not treat a provider/tool `SUCCESS` report as proof of realized authoritative state.
- Do not broaden an `ExecutionEnvelope` through planning or delegated realization.
- Do not resume a terminal failed attempt.
- Do not introduce automatic retry after admission, dispatch, actual effect, possible effect, or unknown effect.
- Do not remove retained negative projection decisions or evidence merely because the final state appears correct.

## Agent-harness boundary

`AGENTS.md` and `.agents/skills/` are operating instructions for compatible agents.

They are not a non-bypassable security mechanism.

Do not claim that repository instructions alone guarantee model compliance, sandboxing, capability security, or production containment.

## Verification

For behavioral changes:

```bash
python -m pytest -q
```

The current baseline is:

```text
148 passed
```

Run targeted tests first when useful, then run the full suite before reporting completion.

Examples should remain independently runnable:

```bash
python examples/success_path.py
python examples/false_success_path.py
```

## Reporting

When completing a bounded task, report:

```text
files changed
requirements affected
behavior changed or preserved
tests executed
test result
remaining uncertainty / carry-forward
```

Do not declare architecture acceptance, production readiness, canon status, or release approval on the basis of your own work.

## Public/private boundary

This public repository must remain self-contained.

Do not introduce dependencies on private workspaces, private execution records, private provenance corpora, local absolute paths, credentials, or unpublished architecture packages.

If a requested change requires unavailable private material, report that dependency instead of reconstructing it from inference.

## Specialized procedure

For tasks that affect GSRR state-realization semantics, use:

```text
.agents/skills/gsrr-state-realization/SKILL.md
```
