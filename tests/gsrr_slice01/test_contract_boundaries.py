"""Additional tests of DS-named reference and evidence seams."""
from dataclasses import FrozenInstanceError, replace
import pytest
from gsrr_slice01.contracts import AuthorityEvidence, Control, Gate, Mode, Outcome, RetryPolicy
from gsrr_slice01.fixture import FixtureFaults
from gsrr_slice01.journal import RetentionError
from gsrr_slice01.runtime import SliceRuntime
from gsrr_slice01.governance import validate_plan
from test_runtime import exercise, event_names, assert_no_effect, RETRY


def test_rs_v05_repeated_executor_entry_is_historical(capture):
    """S01-R10/R11: executor re-entry also performs duplicate lookup before freshness."""
    r,x=exercise(capture)
    reads=r.provider.read_count
    events=r.journal.aggregate.events
    again=r.dispatch()
    assert again.disposition=="HISTORICAL_RETRIEVAL"
    assert again.projection is x.projection
    assert r.provider.read_count==reads and r.journal.aggregate.events==events
    changed=replace(x.commit.dispatch_payload,object_id="OTHER")
    assert r.dispatch(changed).disposition=="REFUSED_DUPLICATE"
    assert r.provider.invocation_count==1
    capture(r,"reentry")


@pytest.mark.parametrize("fault", ["forbidden","postconditions","evidence","capability","mode_support"])
def test_s01_t04_complete_envelope_and_descriptor(capture,fault):
    """S01-R06/R08/R26: complete obligations and registration semantics are independently checked."""
    from gsrr_slice01.governance import build_instruction
    r=SliceRuntime()
    assert r.prepare()
    original=r.envelope
    if fault in ("forbidden","postconditions","evidence"):
        field={"forbidden":"forbidden_effects","postconditions":"postconditions",
               "evidence":"reconciliation_requirements"}[fault]
        e=replace(original,envelope_id=r.journal.new_id("envelope"),**{field:()})
        r.journal.retain(e.envelope_id,e)
    else:
        e=original
        cap=replace(r.cap_descriptor,descriptor_id=r.journal.new_id("descriptor"),
                    **({"capability_id":"OTHER"} if fault=="capability" else
                       {"supported_realization_modes":()}))
        r.journal.retain(cap.descriptor_id,cap)
        r.cap_descriptor=cap
    p=build_instruction(r.journal,e,r.supervisor.current.attempt_id,Mode.EXPLICIT_PLAN)
    v=validate_plan(r.journal,p,e,r.approval,r.definition,r.cap_descriptor,r.supervisor.current.attempt_id)
    assert v.disposition==Gate.REFUSED
    assert r.provider.invocation_count==0 and r.commit is None
    assert r.journal.get(original.envelope_id)==original
    capture(r)


def test_rs_v03_validation_for_other_plan_cannot_admit(capture):
    """S01-R08/R09/R11: a passing validation must bind the exact admitted plan identity."""
    from gsrr_slice01.governance import build_instruction
    r=SliceRuntime()
    assert r.prepare()
    p=build_instruction(r.journal,r.envelope,r.supervisor.current.attempt_id,Mode.EXPLICIT_PLAN)
    r.plan_validation=validate_plan(r.journal,p,r.envelope,r.approval,r.definition,r.cap_descriptor,r.supervisor.current.attempt_id)
    r.plan=build_instruction(r.journal,r.envelope,r.supervisor.current.attempt_id,Mode.EXPLICIT_PLAN)
    with pytest.raises(RetentionError,match="exact active plan"):
        r.admit("key-1")
    assert r.commit is None and r.provider.invocation_count==0
    capture(r)


def test_s01_t07_old_plan_human_approval_not_transferable(capture):
    """S01-R23/R27/T07-V03: unchanged WHAT does not transfer old-plan-specific human evidence."""
    from gsrr_slice01.governance import build_instruction
    r=SliceRuntime(policy=RETRY)
    assert r.prepare()
    r.plan=build_instruction(r.journal,r.envelope,r.supervisor.current.attempt_id,Mode.EXPLICIT_PLAN,"target")
    v=validate_plan(r.journal,r.plan,r.envelope,r.approval,r.definition,r.cap_descriptor,r.supervisor.current.attempt_id)
    r.grant=AuthorityEvidence(evidence_id="plan-grant",human_required=True,
        subject_ref=r.plan.plan_id,policy_ref="human-policy",decision="APPROVE",
        human_issuer="fixture-human-issuer")
    r.retain_grant()
    r.supervisor.fail(Control.REJECT_RETRYABLE,"GENERATED_PLAN_ENVELOPE_VIOLATION",(v.plan_validation_id,))
    control,checks,_,_=r.fresh(retry=True)
    assert control==Control.HUMAN_AUTHORIZATION_REQUIRED
    assert r.supervisor.successor(r.supervisor.current.attempt_id,Mode.EXPLICIT_PLAN,
                                   control,r.record_checks(checks)) is None
    assert len(r.supervisor.attempts)==1 and r.provider.invocation_count==0
    capture(r)


def test_rs_v02_conflicting_observations_both_retained(capture):
    """S01-R13/R14: conflicting evidence means two actual incompatible immutable observations."""
    r,x=exercise(capture,faults=FixtureFaults(observation_fault="conflicting"))
    other=r.journal.get(r.observed.conflicting_snapshot_ref)
    assert other.observation_version==r.observed.observation_version
    assert other.state!=r.observed.state
    assert any(other.snapshot_id in c.observed_input_refs for c in x.reconciliation.checks)
    assert x.reconciliation.outcome==Outcome.RECONCILIATION_AMBIGUOUS


def test_s01_t07_disabled_class_and_immutable_policy(capture):
    """S01-R22/R24: an unsupported class is not enabled by merely setting retry_enabled."""
    policy=RetryPolicy(retry_enabled=True,max_attempts=2,allowed_failure_classes=())
    r,x=exercise(capture,policy=policy,faults=FixtureFaults(plan_defects=("target",)))
    assert x.control==Control.FAIL_NONRETRYABLE
    assert len(r.supervisor.attempts)==1
    assert "CircuitOpened" not in event_names(r)
    with pytest.raises(FrozenInstanceError):
        policy.max_attempts=99
    assert_no_effect(r,x)
