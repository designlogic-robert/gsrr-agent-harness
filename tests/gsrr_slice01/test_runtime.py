"""Accepted DS behavioral tests. Requirement links are also mapped in evidence."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pytest
from gsrr_slice01.contracts import (
    AuthorityEvidence, Control, ControlPayload, Decision, ExecutionPlan,
    Gate, Mode, Outcome, Report, RetryPolicy, RuntimeEvent, plain,
)
from gsrr_slice01.fixture import ActionRequest, FixtureFaults, RequestPort
from gsrr_slice01.journal import RetentionError
from gsrr_slice01.runtime import Request, SliceRuntime
from gsrr_slice01.governance import validate_plan

RETRY = RetryPolicy(retry_enabled=True, max_attempts=2)


def exercise(capture, *, faults=FixtureFaults(), request=Request(), **kwargs):
    runtime = SliceRuntime(faults=faults, **kwargs)
    result = runtime.run(request)
    capture(runtime)
    return runtime, result


def event_names(runtime):
    return [e.event_type for e in runtime.journal.aggregate.events]


def assert_trace(runtime):
    events = runtime.journal.aggregate.events
    assert [e.sequence for e in events] == list(range(1, len(events) + 1))
    assert len({e.event_id for e in events}) == len(events)
    for i, event in enumerate(events):
        assert event.causation_id_or_null == (events[i - 1].event_id if i else None)
        for ref in event.artifact_refs:
            assert runtime.journal.get(ref) is not None
    records = runtime.journal.aggregate.records
    assert len({key for key, _ in records}) == len(records)
    assert runtime.journal.get(runtime.original_definition.definition_id) == runtime.original_definition


def assert_no_effect(runtime, result):
    assert runtime.provider.invocation_count == 0
    assert runtime.provider.actions == ()
    assert result.execution is None
    assert result.reconciliation is None
    assert result.projection is None
    assert "ExecutionCompleted" not in event_names(runtime)
    assert "StateProjected" not in event_names(runtime)


def assert_negative(runtime, result, decision=None):
    assert result.projection is not None
    assert result.projection.final_decision != Decision.PROJECT
    if decision:
        assert result.projection.final_decision == decision
    assert not result.projection.authoritative_state_changed
    assert "StateProjected" not in event_names(runtime)
    assert runtime.provider.invocation_count == 1
    assert all(a.terminal for a in runtime.supervisor.attempts)
    assert_trace(runtime)


def test_s01_t01_success(capture):
    """S01-R01..R21: full separate governance/effect/reconciliation/publication chain."""
    r, x = exercise(capture)
    assert x.control == Control.PASS
    assert x.reconciliation.outcome == Outcome.RECONCILED_SUCCESS
    assert x.projection.final_decision == Decision.PROJECT
    assert x.projection.write_outcome == "APPLIED"
    assert r.provider.invocation_count == 1
    assert r.provider.view.state == r.journal.aggregate.authority_state == "REVIEW"
    assert r.provider.view.version == r.journal.aggregate.authority_version == 2
    assert r.provider.view.digest == "fixture-content-digest"
    assert len(r.provider.actions) == 1
    assert r.provider.actions[0].invocation_id == x.commit.commit_id
    assert r.provider.view.predecessor == 1
    assert x.commit.dispatch_payload.invocation_id == x.commit.commit_id
    assert x.commit.attempt_id == r.plan.attempt_id == r.plan_validation.attempt_id
    assert x.projection.retention_ref in dict(r.journal.aggregate.outcome_slots)
    assert len(set(r.journal.artifact_types())) == 15
    assert all(r.journal.get(ref) is not None for ref in x.projection.initial_and_current_snapshot_refs)
    order = event_names(r)
    for a, b in zip(["IntentStructured","CandidateSelected","TransitionValidated",
                     "TransitionAuthorized","ExecutionPlanValidated","TransitionCommitted",
                     "ExecutionCompleted","TransitionReconciled"],
                    ["CandidateSelected","TransitionValidated","TransitionAuthorized",
                     "ExecutionPlanValidated","TransitionCommitted","ExecutionCompleted",
                     "TransitionReconciled","StateProjected"]):
        assert order.index(a) < order.index(b)
    assert r.plan.sufficiency_policy_ref == x.reconciliation.sufficiency_policy_ref == "sufficiency-profile-1"
    assert_trace(r)


@pytest.mark.parametrize("fault", [
    FixtureFaults(initial_read_missing=True), FixtureFaults(candidate_count=0),
    FixtureFaults(candidate_count=2), FixtureFaults(selection_unknown=True),
    FixtureFaults(missing_intent=True), FixtureFaults(missing_profile=True),
], ids=["missing-read","empty-pool","multiple-pool","unknown-selection","missing-identity","missing-profile"])
def test_s01_t01_input_and_nonselection(capture, fault):
    """S01-R01/R02/R03/R18: unavailable input is not a fabricated positive artifact."""
    r, x = exercise(capture, faults=fault)
    assert x.control == Control.HOLD_AMBIGUOUS
    assert_no_effect(r, x)
    assert x.commit is None
    if fault.initial_read_missing:
        assert "AuthoritativeStateSnapshot" not in r.journal.artifact_types()
    if fault.candidate_count != 1 or fault.selection_unknown:
        selection = next(v for _, v in r.journal.aggregate.records if type(v).__name__ == "CandidateSelection")
        assert selection.selected_transition_id_or_null is None
        assert selection.disposition == "NO_SELECTION"
        assert "CandidateSelected" not in event_names(r)


@pytest.mark.parametrize("target", ["APPROVED", "PUBLISHED"])
def test_s01_t02_invalid_what(capture, target):
    """S01-R04/R21/R22: changing requested WHAT is never eligible plan regeneration."""
    r, x = exercise(capture, request=Request(target_state=target), policy=RETRY)
    assert x.control == Control.FAIL_NONRETRYABLE
    assert_no_effect(r, x)
    assert x.commit is None and r.approval is None
    assert len(r.supervisor.attempts) == 1 and r.supervisor.current.terminal
    assert "CandidateSelected" in event_names(r)


@pytest.mark.parametrize("grant", [
    None, replace(AuthorityEvidence(), active=False),
    replace(AuthorityEvidence(), issuer_id="wrong"),
    replace(AuthorityEvidence(), object_id="OTHER"),
    replace(AuthorityEvidence(), source_authority_version=2),
], ids=["missing","inactive","wrong-issuer","wrong-object","wrong-version"])
def test_s01_t03_insufficient_authority(capture, grant):
    """S01-R05/R27: selection and validity do not supply a grant."""
    r, x = exercise(capture, grant=grant, policy=RETRY)
    assert x.control == Control.FAIL_NONRETRYABLE
    assert x.commit is None
    assert_no_effect(r, x)
    assert len(r.supervisor.attempts) == 1


@pytest.mark.parametrize("kind,expected", [
    ("unknown", Control.HOLD_AMBIGUOUS),
    ("reserved", Control.HUMAN_AUTHORIZATION_REQUIRED),
    ("bound", Control.PASS),
    ("mutated", Control.HUMAN_AUTHORIZATION_REQUIRED),
])
def test_s01_t03_human_subject_and_unknown(capture, kind, expected):
    """S01-R05/R27: explicit policy, exact subject, False versus None."""
    grant = AuthorityEvidence(active=None) if kind == "unknown" else AuthorityEvidence(
        human_required=True, subject_ref="request-1" if kind == "bound" else "old-subject",
        policy_ref="human-policy", decision="APPROVE" if kind != "reserved" else None,
        human_issuer="fixture-human-issuer")
    r, x = exercise(capture, grant=grant)
    assert x.control == expected
    if expected != Control.PASS:
        assert_no_effect(r, x)
    else:
        assert x.projection.final_decision == Decision.PROJECT


@pytest.mark.parametrize("mode", list(Mode))
@pytest.mark.parametrize("defect,expected", [
    ("target", Control.FAIL_NONRETRYABLE), ("object", Control.FAIL_NONRETRYABLE),
    ("implementation", Control.FAIL_NONRETRYABLE), ("extra_step", Control.FAIL_NONRETRYABLE),
    ("source", Control.FAIL_NONRETRYABLE), ("obligations", Control.HOLD_AMBIGUOUS),
    ("infeasible", Control.HOLD_AMBIGUOUS),
])
def test_s01_t04_plan_and_delegated_bounds(capture, mode, defect, expected):
    """S01-R06/R07/R08/R26: reject scope expansion and hold missing complete obligations."""
    r, x = exercise(capture, request=Request(mode=mode),
                    faults=FixtureFaults(plan_defects=(defect,)))
    assert x.control == expected
    assert_no_effect(r, x)
    assert x.commit is None
    assert len(r.supervisor.attempts) == 1
    assert r.journal.aggregate.authority_state == "DRAFT"


@pytest.mark.parametrize("mode", list(Mode))
def test_s01_t05_false_native_success(capture, mode):
    """S01-R12/R13/R14/R15/R26: complete unchanged baseline is FAILED, not stale."""
    r, x = exercise(capture, request=Request(mode=mode),
                    faults=FixtureFaults(actions=()))
    assert x.execution.reported_status == Report.SUCCESS
    assert x.reconciliation.outcome == Outcome.RECONCILIATION_FAILED
    assert_negative(r, x, Decision.DO_NOT_PROJECT)
    assert r.journal.aggregate.authority_state == r.provider.view.state == "DRAFT"
    assert x.projection.current_authority_version_or_null is None
    assert any("NOT_EVALUATED" in c.reason for c in x.projection.checks)


@pytest.mark.parametrize("seam", ["pre_commit","pre_dispatch","post_execution","final"])
@pytest.mark.parametrize("kind", ["authority","observation"])
def test_s01_t06_freshness_seams(capture, seam, kind):
    """S01-R02/R20: immutable original bindings, own effect versus unrelated change."""
    r, x = exercise(capture, faults=FixtureFaults(injections=((seam, kind),)))
    assert x.control == Control.HOLD_AMBIGUOUS
    assert "StateProjected" not in event_names(r)
    assert r.envelope.source_authority_version == r.envelope.source_observation_version == 1
    if seam in ("pre_commit", "pre_dispatch"):
        assert_no_effect(r, x)
        assert (x.commit is None) == (seam == "pre_commit")
        if x.commit:
            assert r.supervisor.ledger.admission_seen is True
    else:
        assert_negative(r, x, Decision.HOLD_PROJECTION)
    assert r.journal.aggregate.authority_state == ("REVIEW" if kind == "authority" else "DRAFT")


def test_s01_t07_exhaustion_and_immutable_terminality(capture):
    """S01-R21..R25: max two attempts, immutable failure events, no third allocation."""
    r, x = exercise(capture, policy=RETRY, faults=FixtureFaults(plan_defects=("target","target")))
    assert x.control == Control.CIRCUIT_OPEN
    assert len(r.supervisor.attempts) == 2
    a, b = r.supervisor.attempts
    assert a.terminal and b.terminal
    assert a.attempt_id != b.attempt_id and b.prior_attempt_id == a.attempt_id
    assert [a.attempt_number,b.attempt_number] == [1,2]
    assert len({p.plan_id for p in r.plans}) == len({v.plan_validation_id for v in r.validations}) == 2
    assert r.plans[0].envelope_id == r.plans[1].envelope_id == r.envelope.envelope_id
    assert r.supervisor.ledger.attempts_created == 2
    assert r.supervisor.ledger.circuit_state == "OPEN"
    assert_no_effect(r, x)
    assert "CircuitOpened" in event_names(r) and "HumanEscalationRequired" in event_names(r)
    frozen_history = r.journal.aggregate.events
    assert r.supervisor.successor(a.attempt_id, Mode.EXPLICIT_PLAN, Control.PASS, ("fixture-boundary",)).attempt_id == b.attempt_id
    assert r.journal.aggregate.events == frozen_history
    assert r.run(key="new-key").disposition == "NO_SCOPE_RESET"
    with pytest.raises(RetentionError):
        r.supervisor.admission()
    assert_trace(r)


def test_s01_t07_corrected_successor_no_ai_approval(capture):
    """T07-V01/V09; S01-R21..R25/R27: corrected B is new, ordinary automation needs no human."""
    r, x = exercise(capture, policy=RETRY, faults=FixtureFaults(plan_defects=("target","")))
    assert x.projection.final_decision == Decision.PROJECT
    assert r.supervisor.attempts[0].terminal
    assert x.commit.attempt_id == r.supervisor.attempts[1].attempt_id
    assert r.provider.invocation_count == 1
    assert r.planner.calls == 2
    assert not any(e.outcome == Control.HUMAN_AUTHORIZATION_REQUIRED for e in r.journal.aggregate.events)
    assert r.journal.get(r.supervisor.attempts[0].attempt_id + ":terminal").terminal


@pytest.mark.parametrize("kind", [
    "authority","observation","content","definition","target","envelope","grant_inactive",
    "grant_unknown","human_reserved","approval_subject","admitted","unknown_admission",
    "possible_effect","occurred_effect","unknown_effect","dispatch","missing_read",
])
def test_s01_t07_fresh_recheck_and_effect_boundaries(capture, kind):
    """T07-V03/V04/V05; S01-R22/R23: unknown is not established no-effect."""
    r, x = exercise(capture, policy=RETRY, faults=FixtureFaults(
        plan_defects=("target",), injections=(("retry",kind),)))
    assert len(r.supervisor.attempts) == 1
    assert r.supervisor.current.terminal
    assert_no_effect(r, x)
    assert x.control in (Control.HOLD_AMBIGUOUS,Control.FAIL_NONRETRYABLE,Control.HUMAN_AUTHORIZATION_REQUIRED)


@pytest.mark.parametrize("policy", [
    None, RetryPolicy(retry_enabled=True,max_attempts=0),
    RetryPolicy(retry_enabled=True,max_attempts=True),
    RetryPolicy(retry_enabled=True,max_attempts=None),
    RetryPolicy(retry_enabled=True,max_attempts=float("inf")),
    RetryPolicy(retry_enabled=True,repeated_failure_threshold_or_null=0),
])
def test_s01_t07_invalid_finite_policy(capture, policy):
    """T07-V06; S01-R24: invalid/unbounded policy never guesses a budget."""
    r, x = exercise(capture, policy=policy, faults=FixtureFaults(plan_defects=("target",)))
    assert x.control == Control.HOLD_AMBIGUOUS
    assert_no_effect(r, x)
    assert len(r.supervisor.attempts) == 1


@pytest.mark.parametrize("fault", [
    FixtureFaults(plan_defects=("target",),failure_evidence_missing=True),
    FixtureFaults(plan_defects=("target",),scheduling_failure=True),
])
def test_s01_t07_missing_failure_or_schedule_evidence(capture, fault):
    """T07-V06/V07; S01-R25: no activation or refund from incomplete evidence."""
    r, x = exercise(capture, policy=RETRY, faults=fault)
    assert x.control == Control.HOLD_AMBIGUOUS
    assert len(r.supervisor.attempts) == 1
    assert r.supervisor.ledger.attempts_created == 1
    assert_no_effect(r, x)


def test_s01_t07_threshold_before_spare_budget(capture):
    """T07-V08; S01-R24: count terminal failed attempts, not events."""
    r, x = exercise(capture, policy=RetryPolicy(
        retry_enabled=True,max_attempts=3,repeated_failure_threshold_or_null=1),
        faults=FixtureFaults(plan_defects=("target",)))
    assert x.control == Control.CIRCUIT_OPEN
    assert len(r.supervisor.attempts) == r.supervisor.ledger.attempts_created == 1
    assert_no_effect(r, x)


def test_s01_t08_same_what_distinct_how(capture):
    """S01-R26 and R01/R02/R05/R06/R08/R09/R11..R21/R27: isolated immutable-prefix alternatives."""
    prefix = SliceRuntime()
    assert prefix.prepare()
    approved = (plain(prefix.transition), plain(prefix.approval), plain(prefix.envelope))
    a, b = deepcopy(prefix), deepcopy(prefix)
    x = a.realize(mode=Mode.EXPLICIT_PLAN)
    y = b.realize(mode=Mode.DELEGATED_REALIZATION)
    capture(a,"explicit")
    capture(b,"delegated")
    assert (plain(a.transition),plain(a.approval),plain(a.envelope)) == approved
    assert (plain(b.transition),plain(b.approval),plain(b.envelope)) == approved
    assert "realization_mode" not in plain(a.envelope)
    assert a.planner.calls == 1 and b.planner.calls == 0
    assert a.capability.internal_planning_calls == 0 and b.capability.internal_planning_calls == 1
    assert a.plan.producer == "PLANNER" and b.plan.producer == "GSRR_SLICE_01"
    assert a.plan.realization_mode != b.plan.realization_mode
    assert a.plan.steps == b.plan.steps
    for runtime, result in [(a,x),(b,y)]:
        assert result.reconciliation.outcome == Outcome.RECONCILED_SUCCESS
        assert result.projection.final_decision == Decision.PROJECT
        assert runtime.provider.view.version == runtime.journal.aggregate.authority_version == 2
        assert runtime.provider.invocation_count == 1
        assert runtime.provider.view.state == runtime.journal.aggregate.authority_state == "REVIEW"
        assert runtime.observed.complete_for_invocation
        assert len(runtime.observed.actions) == 1
        assert_trace(runtime)
    assert prefix.provider.invocation_count == 0
    assert prefix.journal.aggregate.authority_state == "DRAFT"


def test_s01_t08_delegated_planning_failure_no_retry(capture):
    """S01-R21/R22/R26: provider-internal planning after admission is not retryable."""
    r, x = exercise(capture, request=Request(mode=Mode.DELEGATED_REALIZATION),
                    policy=RETRY, faults=FixtureFaults(delegated_planning_failure=True))
    assert x.execution.reported_status == Report.FAILURE
    assert_negative(r, x, Decision.DO_NOT_PROJECT)
    assert len(r.supervisor.attempts) == 1
    assert r.provider.actions == ()
    assert r.supervisor.ledger.admission_seen


FORBIDDEN = [
    (ActionRequest("CONTENT_WRITE","changed"),ActionRequest("CONTENT_WRITE","fixture-content-digest"),ActionRequest("STATE","REVIEW")),
    (ActionRequest("EXISTS","false"),ActionRequest("EXISTS","true"),ActionRequest("STATE","REVIEW")),
    (ActionRequest("STATE","APPROVED"),ActionRequest("STATE","REVIEW")),
    (ActionRequest("STATE","PUBLISHED"),ActionRequest("STATE","REVIEW")),
    (ActionRequest("STATE","REVIEW","OTHER"),),
    (ActionRequest("DEFINITION_WRITE","anything"),),
    (ActionRequest("NESTED_DISPATCH","anything"),),
    (ActionRequest("NETWORK","anything"),),
]


@pytest.mark.parametrize("mode", list(Mode))
@pytest.mark.parametrize("actions", FORBIDDEN, ids=[
    "mutate-restore","delete-recreate","approved-review","published-review",
    "wrong-object","definition-write","nested-dispatch","network"])
def test_rs_v01_forbidden_history(capture, mode, actions):
    """S01-R06/R11/R13/R15/R26: transient/denied actions cannot disappear in final digest."""
    r, x = exercise(capture, request=Request(mode=mode),faults=FixtureFaults(
        actions=actions,allow_invalid_writes=True))
    assert x.reconciliation.outcome == Outcome.RECONCILIATION_FAILED
    assert_negative(r,x,Decision.DO_NOT_PROJECT)
    assert len(r.provider.actions) == len(actions)
    assert x.reconciliation.forbidden_effect_findings
    assert r.journal.aggregate.authority_state == "DRAFT"
    if actions[0].kind in ("DEFINITION_WRITE","NESTED_DISPATCH","NETWORK") or actions[0].object_id == "OTHER":
        assert not any(a.applied for a in r.provider.actions)
    if actions[0].kind == "CONTENT_WRITE":
        assert r.provider.view.digest == "fixture-content-digest"
    if actions[0].kind == "EXISTS":
        assert r.provider.view.exists


@pytest.mark.parametrize("fault", ["missing","incomplete","dropped","unclosed"])
def test_rs_v01_missing_independent_interval(capture, fault):
    """S01-R13/R15: target-looking terminal state is insufficient."""
    r,x=exercise(capture,faults=FixtureFaults(observation_fault=fault))
    assert x.execution.reported_status == Report.SUCCESS
    assert x.reconciliation.outcome == Outcome.UNRESOLVED
    assert_negative(r,x,Decision.HOLD_PROJECTION)


@pytest.mark.parametrize("fault,expected", [
    (FixtureFaults(),Outcome.RECONCILED_SUCCESS),
    (FixtureFaults(actions=()),Outcome.RECONCILIATION_FAILED),
    (FixtureFaults(injections=(("post_execution","authority"),)),Outcome.STALE_STATE),
    (FixtureFaults(observation_fault="conflicting"),Outcome.RECONCILIATION_AMBIGUOUS),
    (FixtureFaults(observation_fault="missing"),Outcome.UNRESOLVED),
])
def test_rs_v02_five_reachable_outcomes(capture,fault,expected):
    """S01-R13/R14/R15: each declared outcome has a deterministic witness."""
    r,x=exercise(capture,faults=fault)
    assert x.reconciliation.outcome == expected
    assert "PARTIAL_REALIZATION" not in [e.value for e in Outcome]
    assert x.projection is not None


def test_rs_v02_known_violation_precedence(capture):
    """S01-R14: retain stale/unresolved secondary findings without hiding known violation."""
    r,x=exercise(capture,faults=FixtureFaults(
        actions=FORBIDDEN[0],allow_invalid_writes=True,observation_fault="incomplete",
        injections=(("post_execution","authority"),)))
    assert x.reconciliation.outcome == Outcome.RECONCILIATION_FAILED
    assert x.reconciliation.forbidden_effect_findings
    assert x.reconciliation.unresolved_fields
    assert any(c.criterion_ref=="CURRENT_AUTHORITY" and c.result=="FAIL" for c in x.reconciliation.checks)
    assert_negative(r,x,Decision.DO_NOT_PROJECT)


@pytest.mark.parametrize("field", ["commit_id","idempotency_key","implementation_id","object_id","extra"])
def test_rs_v03_payload_substitution(capture,field):
    """S01-R07/R08/R09/R11: retained finite payload equality before invocation."""
    r,x=exercise(capture,faults=FixtureFaults(payload_substitution=field))
    assert x.commit is not None
    assert_no_effect(r,x)
    assert x.control == Control.FAIL_NONRETRYABLE
    assert r.journal.get(x.commit.commit_id) == x.commit
    assert r.journal.get(r.plan.plan_id) == r.plan
    assert {f.name for f in fields(x.commit.dispatch_payload)} == {
        "object_id","source_state","target_state","expected_observation_version",
        "capability_id","implementation_id","plan_id","envelope_id","commit_id","idempotency_key","invocation_id"}
    with pytest.raises(FrozenInstanceError):
        r.plan.realization_mode=Mode.DELEGATED_REALIZATION


def test_rs_v03_mutation_after_validation(capture):
    """S01-R08/R11/R26: changing HOW after validation cannot reuse admission."""
    r,x=exercise(capture,faults=FixtureFaults(injections=(("pre_dispatch","plan_mode"),)))
    assert x.control == Control.FAIL_NONRETRYABLE
    assert_no_effect(r,x)


def test_rs_v03_missing_commit_record_retention(capture):
    """S01-R09: inability to retain commit/event blocks dispatch."""
    r,x=exercise(capture,faults=FixtureFaults(commit_retention_failure=True))
    assert x.control == Control.HOLD_AMBIGUOUS
    assert x.commit is None
    assert_no_effect(r,x)


@pytest.mark.parametrize("fault", ["write","event","publication"])
def test_rs_v04_publication_negative_retention(capture,fault):
    """S01-R15/R16/R17: one negative retained final decision, no partial authority write."""
    r,x=exercise(capture,faults=FixtureFaults(publication_fault=fault))
    assert x.reconciliation.outcome == Outcome.RECONCILED_SUCCESS
    assert_negative(r,x,Decision.DO_NOT_PROJECT)
    assert x.projection.write_outcome == "FAILED"
    assert x.projection.journal_record_status == ("UNAVAILABLE" if fault=="event" else "RECORDED")
    assert r.journal.aggregate.authority_state == "DRAFT"
    assert r.provider.view.state == "REVIEW"
    assert dict(r.journal.aggregate.outcome_slots)[x.projection.retention_ref] == x.projection
    assert sum(type(v).__name__=="ProjectionDecision" for _,v in r.journal.aggregate.records)==1


def test_rs_v04_retention_unavailable_before_evaluation(capture):
    """S01-R15/R16: no fabricated final evaluation when slot reservation fails."""
    r,x=exercise(capture,faults=FixtureFaults(retention_unavailable=True))
    assert x.reconciliation.outcome == Outcome.RECONCILED_SUCCESS
    assert x.projection is None
    assert r.journal.aggregate.outcome_slots == ()
    assert r.journal.aggregate.authority_state == "DRAFT"
    assert "StateProjected" not in event_names(r)


@pytest.mark.parametrize("kind", ["grant_inactive","grant_unknown","missing_read","observation"])
def test_rs_v04_final_gate_denial(capture,kind):
    """S01-R15/R16: final fresh invalid versus unresolved conditions."""
    r,x=exercise(capture,faults=FixtureFaults(injections=(("final",kind),)))
    assert_negative(r,x,Decision.DO_NOT_PROJECT if kind=="grant_inactive" else Decision.HOLD_PROJECTION)
    assert r.journal.aggregate.authority_state == "DRAFT"


def test_rs_v05_historical_duplicate_before_reads(capture):
    """S01-R02/R10/R20: exact old tuple retrieves old immutable evidence with zero reads."""
    r,x=exercise(capture)
    reads=r.provider.read_count
    events=r.journal.aggregate.events
    original=r.index["key-1"].binding
    again=r.run()
    assert again.disposition=="HISTORICAL_RETRIEVAL"
    assert again.commit is x.commit and again.execution is x.execution and again.projection is x.projection
    assert r.provider.read_count==reads
    assert r.journal.aggregate.events==events
    assert r.provider.invocation_count==1
    assert r.run(binding=original[:-1]+("wrong",)).disposition=="REFUSED_DUPLICATE"
    assert r.run(Request(target_state="APPROVED")).disposition=="REFUSED_DUPLICATE"
    assert r.provider.read_count==reads
    capture(r,"after_duplicates")


def test_rs_v05_incomplete_retained_commit(capture):
    """S01-R10: incomplete historical outcome cannot trigger a new effect."""
    r=SliceRuntime()
    assert r.prepare()
    from gsrr_slice01.governance import build_instruction
    r.plan=build_instruction(r.journal,r.envelope,r.supervisor.current.attempt_id,Mode.EXPLICIT_PLAN)
    r.plan_validation=validate_plan(r.journal,r.plan,r.envelope,r.approval,r.definition,r.cap_descriptor,r.supervisor.current.attempt_id)
    r.admit("key-1")
    reads=r.provider.read_count
    x=r.run()
    assert x.disposition=="HISTORICAL_INCOMPLETE"
    assert r.provider.read_count==reads
    assert r.provider.invocation_count==0
    assert r.supervisor.ledger.admission_seen
    capture(r)


@pytest.mark.parametrize("kind,decision", [
    ("grant_inactive",Decision.DO_NOT_PROJECT),("grant_unknown",Decision.HOLD_PROJECTION)])
def test_rs_v06_grant_change_without_state_version(capture,kind,decision):
    """S01-R05/R15: current external authority must pass even when state versions match."""
    r,x=exercise(capture,faults=FixtureFaults(injections=(("final",kind),)))
    assert x.reconciliation.outcome==Outcome.RECONCILED_SUCCESS
    assert x.projection.current_authority_version_or_null==1
    assert x.projection.current_observation_version_or_null==2
    assert_negative(r,x,decision)


@pytest.mark.parametrize("state_evidence", ["review","draft","incomplete","contradictory"])
def test_mw_d01_unknown_possible_effect_event_not_evidence(capture,state_evidence):
    """MW-D01 NON_NORMATIVE_DIAGNOSTIC; existing R12/R13/R14/R15/R21 only, no new DS state."""
    fault=FixtureFaults(
        reported_status=Report.UNKNOWN,
        actions=() if state_evidence=="draft" else None,
        observation_fault={"incomplete":"missing","contradictory":"conflicting"}.get(state_evidence,""))
    r,x=exercise(capture,policy=RETRY,faults=fault)
    assert x.execution.reported_status==Report.UNKNOWN
    assert "ExecutionCompleted" in event_names(r)
    assert x.reconciliation.outcome==Outcome.RECONCILIATION_AMBIGUOUS
    assert_negative(r,x,Decision.HOLD_PROJECTION)
    assert len(r.supervisor.attempts)==1
    assert r.supervisor.ledger.admission_seen
    assert r.run(key="new-key").disposition=="NO_SCOPE_RESET"
    assert r.provider.invocation_count==1
    if state_evidence=="review":
        assert r.provider.view.state=="REVIEW"
    if state_evidence=="draft":
        assert r.provider.view.state=="DRAFT"
    if state_evidence=="incomplete":
        assert x.reconciliation.observed_snapshot_ref is None
    assert r.journal.aggregate.authority_state=="DRAFT"

