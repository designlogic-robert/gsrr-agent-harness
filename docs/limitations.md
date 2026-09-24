# Scope and Limitations

Version: v0_1  
Status: BOUNDED_PUBLIC_LIMITATION_REGISTER  
Scope: GSRR Operation Core Slice 01  
Production status: NOT_PRODUCTION

## 1. Why the limitations are explicit

Slice 01 is intentionally small.

Its purpose is to make a difficult set of state, authority, execution, evidence and projection distinctions executable and testable without simultaneously solving production deployment, distributed reliability, identity infrastructure, arbitrary-provider trust and learned-model behavior.

Therefore:

```text
implemented
!=
production-ready
```

and:

```text
tested in fixture
!=
proven in arbitrary environment
```

## 2. Synchronous runtime only

The runtime is synchronous.

It does not establish:

```text
asynchronous scheduling correctness
race-condition safety
multi-worker coordination
concurrent mutation safety
```

Introducing concurrency would require separate design and testing.

## 3. In-memory operational state

The fixture is run-local and in-memory.

It does not provide durable production persistence for:

```text
journal records
idempotency state
attempt lineage
projection decisions
provider state
```

Crash/restart persistence and recovery remain outside Slice 01.

## 4. One bounded object and transition

The fixture protects:

```text
Document DOC-001
DRAFT -> REVIEW
```

It does not establish general behavior for:

```text
multiple objects
multiple domains
multi-step workflows
multi-document transactions
arbitrary state graphs
```

Additional domains or transitions require separate scope and evidence.

## 5. Trusted local provider and mediator

The fixture provider and effect mediator are trusted local components.

The ability to reason about a complete action interval depends on that bounded mediation.

This does not prove that a real external provider exposes complete or truthful observation history.

In particular:

```text
local independent observation
!=
proof of arbitrary external-provider truth
```

## 6. No production identity, authorization, or security system

The fixture uses supplied bounded authority evidence.

It does not implement production:

```text
identity proofing
IAM
issuer trust infrastructure
revocation
credential management
tenant isolation
endpoint security
authorization service integration
```

Local equality and reference checks are not cryptographic authorization.

## 7. No arbitrary-host sandbox

The project does not establish a non-bypassable sandbox for arbitrary code or tools.

Fixture actions are bounded because the supplied implementation operates through the local mediator.

That does not prove containment of:

```text
arbitrary subprocesses
filesystem writes outside the fixture
network clients
untrusted plugins
external tool runtimes
```

## 8. No crash durability or restart recovery

The implementation does not prove that a process can crash at arbitrary points and later recover exact:

```text
dispatch state
effect state
idempotency state
reconciliation state
projection state
```

Durable outcome recovery is separate production work.

## 9. No concurrency proof

The fixture's local state mutation semantics do not establish thread, process, or distributed concurrency correctness.

Atomic-looking local assignments are not evidence of transactional concurrency safety.

## 10. No distributed transaction or exactly-once guarantee

Slice 01 does not provide:

```text
distributed transaction guarantees
distributed no-effect proof
exactly-once external execution
cross-service atomic projection
message-delivery guarantees
```

The one-process fixture should not be interpreted as establishing those properties.

## 11. Run-local idempotency only

The runtime can retrieve matching historical results within its retained run-local state.

It does not establish cross-process or durable idempotency after restart.

Production idempotency would require durable key/dispatch/outcome recovery semantics.

## 12. No external-provider completeness guarantee

The fixture can independently observe its own local provider.

That does not prove that a real SaaS/API/tool provider would return:

```text
complete state
complete action history
truthful attribution
consistent snapshots
```

Provider trust and observation contracts must be established separately for each production integration.

## 13. No live-model reliability proof

Deterministic test behavior is used for the core verification surface.

The project does not establish that an LLM will reliably:

```text
produce correct intent
select correct transitions
generate valid plans
follow instructions
preserve constraints
avoid hallucination
```

Learned-model behavior requires separate evaluation.

The core deterministic tests intentionally do not depend on paid LLM credentials.

## 14. No natural-language intent correctness claim

The public Slice begins from structured runtime inputs.

It does not prove that free-form natural-language user intent can always be converted into the correct structured objective or transition.

Natural-language interpretation is a separate boundary.

## 15. No general recovery or compensation implementation

The retry model is deliberately conservative.

A possible, actual, or unknown effect blocks automatic regeneration.

The project does not implement generalized production:

```text
compensation
rollback
saga orchestration
operator recovery workflows
effect repair
```

Suppressing blind retry is not the same as implementing recovery.

## 16. No universal architecture claim

The project demonstrates one architecture for one bounded problem.

It does not claim:

```text
every agent system requires this exact pipeline
every state transition requires fifteen artifact types
GSRR is the only valid governance architecture
the current Slice proves a complete GSRR architecture
```

The public fixture is a testable architecture specimen.

## 17. Responsibility labels are local

Names such as `PCPK`, `DASA`, and `MSP` appear as producer/responsibility labels inside Slice 01.

Their presence does not mean this repository publishes or validates the complete architectures associated with those labels.

Only the responsibilities explicitly represented by this public Slice are in scope.

## 18. Agent instructions are not a hard security boundary

The repository reserves an agent operating surface through `AGENTS.md` and a GSRR Skill.

Text instructions can structure and constrain compatible agent behavior, but they are not inherently non-bypassable technical enforcement.

Therefore the project may claim:

> The harness supplies explicit operating instructions and evidence for evaluating agent conformance.

It must not claim:

> The harness guarantees that an LLM cannot bypass its instructions.

Hard capability enforcement would require additional technical mechanisms.

## 19. Passing tests are bounded evidence

The current 148-test suite is meaningful evidence for the declared fixture.

It is not proof that:

```text
all defects are absent
all implementation paths are correct
production guarantees exist
unmodeled environments behave the same way
```

Verification claims must remain tied to the specification and fixture actually tested.

## 20. Current safe claim

The strongest current public claim is:

> GSRR Operation Core Slice 01 demonstrates, within a deterministic closed fixture, that a proposed document-state transition can pass through distinct selection, validation, authorization, planning, commit, execution, observation, reconciliation and projection boundaries without treating proposal or provider success as authoritative realized state.

Anything materially stronger requires additional evidence.
