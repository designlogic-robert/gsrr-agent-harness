# GSRR Agent Harness

**A bounded, runnable case study in agentic systems design and governed state realization.**

Status: v0.1 formation in progress  
License: Apache License 2.0  
Production status: **NOT_PRODUCTION**

## What this repository demonstrates

This project asks a narrow systems question:

> If a proposed state change is authorized and a tool reports success, what must be established before the target state is accepted as authoritative?

GSRR Operation Core Slice 01 answers that question with an executable closed fixture.

The fixture begins with one document:

```text
DOC-001
authoritative state: DRAFT
```

and one permitted target:

```text
DRAFT -> REVIEW
```

The runtime deliberately keeps the following facts separate:

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

The most important demonstration is the false-success case:

```text
provider reports SUCCESS
        ↓
independent observation still sees DRAFT
        ↓
reconciliation fails
        ↓
REVIEW is not projected
        ↓
authoritative state remains DRAFT
```

A native success result is evidence that an invocation reported success. It is not, by itself, proof that the intended state was realized.

## Why this project exists

The repository is intended to show the path from:

```text
system concern
    ↓
explicit architecture
    ↓
bounded specification
    ↓
executable realization
    ↓
independent tests
```

The Python implementation is evidence that the architecture can be realized as executable behavior inside the declared fixture. It is not a claim that this Slice is a production workflow engine, security boundary, distributed transaction system, or general-purpose state platform.

## Current public layers

### 1. System model

[`specification/slice-01/`](specification/slice-01/)

The public Slice 01 specification contains:

- 27 normative requirements;
- 8 base acceptance-scenario groups;
- 6 diagnostic case groups;
- typed artifact and execution contracts;
- operation and authority/evidence topology.

Start with [`specification/slice-01/README.md`](specification/slice-01/README.md).

### 2. Executable realization

[`src/gsrr_slice01/`](src/gsrr_slice01/)

The implementation is a deterministic Python fixture with:

- one document;
- one allowed state edge;
- one registered capability implementation;
- distinct observed and authoritative state;
- bounded dispatch;
- independent reconciliation;
- retained projection decisions;
- bounded retry/successor behavior.

### 3. Verification

[`tests/gsrr_slice01/`](tests/gsrr_slice01/)

The current public suite contains **148 passing tests** and is executed by GitHub Actions across supported Python versions.

See [`docs/verification.md`](docs/verification.md).

## Core architecture

The primary path is:

```text
request
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
bounded dispatch
  ↓
ExecutionResult
  ↓
independent observation
  ↓
ReconciliationResult
  ↓
ProjectionDecision
  ↓
authoritative state changes only on PROJECT / APPLIED
```

Two rules carry most of the design:

```text
provider success != realized authoritative state
```

and:

```text
reconciliation success != authority
```

Successful reconciliation makes a transition eligible for the final projection gate. It does not itself mutate authoritative state.

For the full explanation, see [`docs/architecture.md`](docs/architecture.md).

## Quick start

Python 3.11 through 3.14 are supported by the current project configuration.

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/designlogic-robert/gsrr-agent-harness.git
cd gsrr-agent-harness
python -m venv .venv
```

Activate it.

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install the project and test dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Run the verification suite:

```bash
python -m pytest -q
```

Expected current baseline:

```text
148 passed
```

The exact execution time is machine-dependent.

## Repository map

```text
gsrr-agent-harness/
├── specification/slice-01/   # bounded public system contract
├── src/gsrr_slice01/         # executable Slice 01 realization
├── tests/gsrr_slice01/       # independent executable verification
├── docs/
│   ├── architecture.md
│   ├── design-evolution.md
│   ├── verification.md
│   └── limitations.md
├── .github/workflows/test.yml
├── pyproject.toml
└── LICENSE
```

The v0.1 repository also reserves an agent operating surface under `AGENTS.md` and `.agents/skills/`; that layer is separate from the Slice runtime itself and must not be confused with hard technical enforcement.

## Read next

- [`docs/architecture.md`](docs/architecture.md) — how the current Slice works.
- [`docs/design-evolution.md`](docs/design-evolution.md) — the design questions that produced the key separations.
- [`docs/verification.md`](docs/verification.md) — what the current evidence supports.
- [`docs/limitations.md`](docs/limitations.md) — what this project explicitly does not establish.
- [`specification/slice-01/README.md`](specification/slice-01/README.md) — the bounded public specification.

## Development and AI collaboration posture

This project was developed through substantial human-AI collaboration.

The primary human contribution is systems reasoning, problem framing, architectural direction, failure-mode identification, constraint formation, review, and acceptance decisions. AI collaborators substantially assisted with formalization, architecture synthesis, implementation generation, tests, and supporting artifacts.

The Python implementation was generated substantially by AI coding agents from the resulting specifications, repository context, and bounded instructions. This repository does not present the implementation as conventional hand-authored Python work.

A fuller contribution and AI disclosure is maintained separately as part of the v0.1 public documentation set.

## Claim boundary

This repository demonstrates one deterministic, synchronous, in-memory fixture.

It does **not** establish production readiness, production IAM/security, crash durability, concurrency safety, distributed guarantees, arbitrary-provider trust, live-model reliability, or universal GSRR correctness.

See [`docs/limitations.md`](docs/limitations.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
