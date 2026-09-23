"""Regression tests retained from implementation hardening of GSRR Slice 01.

These tests preserve established Slice 01 behavior without carrying the private
execution-command history into the public repository.
"""
from dataclasses import replace
import pytest
from gsrr_slice01.contracts import Control, Decision, RetryPolicy
from gsrr_slice01.fixture import FixtureFaults
from gsrr_slice01.runtime import SliceRuntime
from test_runtime import RETRY, assert_no_effect, assert_trace, event_names, exercise


class TupleSubclass(tuple):
    pass


@pytest.mark.parametrize("classes,valid", [
    (None, False), (["GENERATED_PLAN_ENVELOPE_VIOLATION"], False),
    ({"GENERATED_PLAN_ENVELOPE_VIOLATION"}, False),
    ({"GENERATED_PLAN_ENVELOPE_VIOLATION": True}, False), ((123,), False),
    (TupleSubclass(("GENERATED_PLAN_ENVELOPE_VIOLATION",)), False),
    (("GENERATED_PLAN_ENVELOPE_VIOLATION",), True),
], ids=["none", "list", "set", "dict", "nonstring", "tuple-subclass", "valid-tuple"])
def test_s01_t07_rf_impl_01_policy_shape_and_runtime(capture, classes, valid):
    """S01-R21/R22/R24: direct validation and ordinary runtime, with no coercion."""
    policy = RetryPolicy(retry_enabled=True, max_attempts=2, allowed_failure_classes=classes)
    assert policy.valid() is valid
    assert policy.allowed_failure_classes is classes
    runtime, result = exercise(capture, policy=policy,
                               faults=FixtureFaults(plan_defects=("target", "")))
    if valid:
        assert result.projection.final_decision == Decision.PROJECT
        assert len(runtime.supervisor.attempts) == 2
        assert runtime.supervisor.attempts[0].terminal
        assert runtime.provider.invocation_count == 1
    else:
        # Calling run above without catching TypeError proves ordinary fail-closed handling.
        assert result.control == Control.HOLD_AMBIGUOUS
        assert result.commit is None
        assert len(runtime.supervisor.attempts) == 1
        assert runtime.supervisor.current.terminal
        assert runtime.planner.calls == 0
        assert "NewAttemptAuthorized" not in event_names(runtime)
        assert_no_effect(runtime, result)
    assert_trace(runtime)


def retry_basis(runtime):
    event = next(e for e in runtime.journal.aggregate.events
                 if e.event_type == "RetryEligibilityDetermined")
    payload = event.control_payload_or_null
    checks = [c for ref in payload.no_effect_check_refs for c in runtime.journal.get(ref)]
    effect = next(c for c in checks if c.criterion_ref == "NO_ADMISSION_OR_EFFECT")
    ledger_ref, facts_ref, boundary_ref = effect.observed_input_refs
    ledger = runtime.journal.get(ledger_ref)
    facts = dict(runtime.journal.get(facts_ref))
    assert facts["scope_ref"] == ledger.scope_ref == payload.scope_ref
    assert facts["scope_ledger_ref"] == ledger_ref
    assert facts["admission_seen"] is ledger.admission_seen
    assert boundary_ref == "fixture-boundary"
    assert runtime.journal.get(boundary_ref)
    for refs, criterion in [(payload.current_state_check_refs, "FRESH_STATE"),
                            (payload.authority_check_refs, "AUTHORITY")]:
        assert any(c.criterion_ref == criterion for ref in refs for c in runtime.journal.get(ref))
    return event, effect, facts


def test_s01_t07_rf_impl_02_retained_positive_basis(capture):
    """S01-R17/R22/R23/R25: inspect retained inputs, not an event's asserted posture."""
    runtime, result = exercise(capture, policy=RETRY,
                               faults=FixtureFaults(plan_defects=("target", "")))
    event, effect, facts = retry_basis(runtime)
    assert effect.result == "PASS"
    assert facts["admission_seen"] is False
    assert facts["commit_refs"] == facts["dispatch_claims"] == facts["provider_actions"] == ()
    assert facts["provider_invocations"] == 0
    assert facts["provider_current_invocation"] is None
    assert facts["effect_posture"] == "NONE_ESTABLISHED"
    assert event.outcome == Control.REJECT_RETRYABLE
    assert event.sequence < next(e.sequence for e in runtime.journal.aggregate.events
                                 if e.event_type == "NewAttemptAuthorized")
    first, second = runtime.supervisor.attempts
    assert first.terminal and first.attempt_id != second.attempt_id
    assert second.prior_attempt_id == first.attempt_id
    assert result.commit.attempt_id == second.attempt_id
    # Subsequent admission/effects do not rewrite the retained pre-allocation facts.
    assert runtime.supervisor.ledger.admission_seen is True
    assert runtime.provider.invocation_count == 1
    assert_trace(runtime)


@pytest.mark.parametrize("kind,expected", [
    ("possible_effect", "FAIL"), ("occurred_effect", "FAIL"),
    ("unknown_effect", "UNRESOLVED"), ("admitted", "FAIL"),
    ("unknown_admission", "UNRESOLVED"), ("dispatch", "FAIL"),
])
def test_s01_t07_rf_impl_02_negative_basis(capture, kind, expected):
    """S01-R21/R22/R23/R25: known/unknown boundaries cannot retain a passing basis."""
    runtime, result = exercise(capture, policy=RETRY, faults=FixtureFaults(
        plan_defects=("target",), injections=(("retry", kind),)))
    event, effect, facts = retry_basis(runtime)
    assert effect.result == expected
    assert event.outcome != Control.REJECT_RETRYABLE
    assert facts["admission_seen"] is not False or facts["effect_posture"] != "NONE_ESTABLISHED"
    assert len(runtime.supervisor.attempts) == 1 and runtime.supervisor.current.terminal
    assert "NewAttemptAuthorized" not in event_names(runtime)
    assert_no_effect(runtime, result)
    assert_trace(runtime)


@pytest.mark.parametrize("kind", ["dispatch_claim", "provider_invocation", "retained_commit"])
def test_s01_t07_rf_impl_02_local_facts_override_clear_flag(capture, kind):
    """S01-R21/R23/R25: NONE_ESTABLISHED alone cannot override actual local evidence."""
    runtime = SliceRuntime(policy=RETRY, faults=FixtureFaults(plan_defects=("target",)))
    assert runtime.prepare()
    if kind == "dispatch_claim":
        runtime.dispatch_claims.add("already-claimed")
    elif kind == "provider_invocation":
        runtime.provider.open_interval("already-started")
    else:
        # Use a real retained commit from the same deterministic scope binding.
        prior = SliceRuntime(policy=RETRY)
        prior.run()
        assert prior.commit.execution_envelope_id == runtime.envelope.envelope_id
        commit = replace(prior.commit, commit_id="retained-prior-commit")
        runtime.journal.retain(commit.commit_id, commit)
    assert runtime.supervisor.ledger.admission_seen is False
    assert runtime.supervisor.effect_posture == "NONE_ESTABLISHED"
    result = runtime.realize()
    capture(runtime)
    event, effect, facts = retry_basis(runtime)
    assert effect.result == "FAIL" and result.control == Control.FAIL_NONRETRYABLE
    assert facts["dispatch_claims"] or facts["provider_invocations"] or facts["commit_refs"]
    assert event.outcome == Control.FAIL_NONRETRYABLE
    assert len(runtime.supervisor.attempts) == 1
    assert result.commit is None and result.execution is None
    assert "NewAttemptAuthorized" not in event_names(runtime)
