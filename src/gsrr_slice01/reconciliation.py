"""Evidence comparison and conditional local authoritative publication."""
from dataclasses import replace
from .contracts import (
    Check, Control, Report, Outcome, Decision, ReconciliationResult, ProjectionDecision,
    RuntimeEvent,
)
from .governance import check, PROFILE


def reconcile(journal, envelope, before, baseline, result, observed, authority_version):
    forbidden = []
    unresolved = []
    stale = authority_version != before.authority_version
    ambiguous = result.reported_status == Report.UNKNOWN
    actions = observed.actions if observed and observed.actions is not None else ()
    for a in actions:
        if (a.reason == "FORBIDDEN_REQUEST" or a.object_id != envelope.object_id
                or a.action_kind != "STATE" or a.requested_value != "REVIEW"
                or a.before_digest != a.after_digest or a.before_exists != a.after_exists):
            forbidden.append(f"action:{a.sequence}:{a.action_kind}:{a.requested_value}")
    complete = bool(
        observed is not None and observed.interval_closed is True
        and observed.complete_for_invocation is True and observed.actions is not None
        and observed.action_log_ref == result.action_interval_ref
        and observed.interval_end - observed.interval_start == len(actions)
    )
    if complete:
        try:
            complete = journal.get(observed.action_log_ref) == actions
        except KeyError:
            complete = False
    if not complete:
        unresolved.append("closed_action_interval")
    if observed is None:
        unresolved.append("observed_snapshot")
    else:
        if observed.conflicting:
            try:
                alternate = journal.get(observed.conflicting_snapshot_ref)
                ambiguous = ambiguous or (
                    alternate.observation_version == observed.observation_version
                    and (alternate.state, alternate.content_digest, alternate.exists)
                    != (observed.state, observed.content_digest, observed.exists)
                )
            except KeyError:
                unresolved.append("conflicting_observation_evidence")
        # Unchanged baseline with no effect is a known mismatch, not an unrelated write.
        own = observed.commit_id == result.commit_id
        unchanged = (
            observed.state == baseline.state
            and observed.observation_version == baseline.observation_version
            and observed.commit_id == baseline.commit_id
        )
        stale = stale or not own and not unchanged
    identity = bool(
        observed and observed.object_id == envelope.object_id
        and observed.provider_id == "STATE_PROVIDER"
        and observed.fixture_boundary_ref == envelope.fixture_boundary_ref
        and result.commit_id == result.invocation_id
        and result.object_id == envelope.object_id
        and all(a.invocation_id == result.commit_id for a in actions)
    )
    target = bool(
        observed and observed.state == envelope.target_state and observed.exists
        and observed.content_digest == baseline.content_digest
        and observed.observation_version == baseline.observation_version + 1
        and observed.predecessor_version == baseline.observation_version
        and observed.commit_id == result.commit_id and len(actions) == 1
        and actions[0].applied and actions[0].before_version == baseline.observation_version
        and actions[0].after_version == baseline.observation_version + 1
    )
    if forbidden or result.reported_status == Report.FAILURE:
        outcome = Outcome.RECONCILIATION_FAILED
    elif stale:
        outcome = Outcome.STALE_STATE
    elif ambiguous:
        outcome = Outcome.RECONCILIATION_AMBIGUOUS
    elif unresolved:
        outcome = Outcome.UNRESOLVED
    elif not identity or not target:
        outcome = Outcome.RECONCILIATION_FAILED
    else:
        outcome = Outcome.RECONCILED_SUCCESS
    refs = (result.result_id,) + ((observed.snapshot_id,) if observed else ())
    if observed and observed.conflicting_snapshot_ref:
        refs += (observed.conflicting_snapshot_ref,)
    checks = (
        check("ACTION_COMPLETENESS", True if complete else None, refs, "provider-owned closed interval"),
        check("NO_FORBIDDEN_ACTION", False if forbidden else True if complete else None, refs,
              "all requested actions, including denied actions"),
        check("CURRENT_AUTHORITY", not stale, refs, "original authority and own observation lineage"),
        check("ATTRIBUTION", None if ambiguous else True, refs, "conflicting/unknown attribution"),
        check("TARGET_POSTCONDITIONS", target if complete and not ambiguous else None, refs,
              "independent state and complete required effect"),
    )
    r = ReconciliationResult(
        **journal.common("RECONCILER"), reconciliation_id=journal.new_id("reconciliation"),
        commit_id=result.commit_id, approval_id=envelope.approval_id, result_id=result.result_id,
        before_snapshot_id=before.snapshot_id,
        observed_snapshot_ref=observed.snapshot_id if observed else None,
        object_id=envelope.object_id, authority_version_checked=authority_version,
        observed_version=observed.observation_version if observed else None,
        observed_predecessor_version=observed.predecessor_version if observed else None,
        observed_commit_id=observed.commit_id if observed else None,
        checks=checks, required_effect_findings=("TARGET_MATCH" if target else "TARGET_NOT_ESTABLISHED",),
        forbidden_effect_findings=tuple(forbidden),
        postcondition_findings=("IDENTITY_MATCH" if identity else "IDENTITY_NOT_ESTABLISHED",),
        outcome=outcome, unresolved_fields=tuple(unresolved), sufficiency_policy_ref=PROFILE,
        action_interval_ref=observed.action_log_ref if observed else None,
        fixture_boundary_ref=envelope.fixture_boundary_ref,
        completeness_findings=("COMPLETE" if complete else "UNRESOLVED",),
        invocation_binding_checks=(check("INVOCATION_BINDING", identity, refs, "exact invocation"),),
    )
    journal.retain(r.reconciliation_id, r)
    return r


def project(runtime):
    j, r = runtime.journal, runtime.reconciliation
    e, commit = runtime.envelope, runtime.commit
    retention = j.new_id("outcome-slot")
    if not j.reserve(retention, (r.reconciliation_id, commit.commit_id),
                     runtime.faults.retention_unavailable):
        runtime.stop(Control.HOLD_AMBIGUOUS, "OUTCOME_RETENTION_UNAVAILABLE", (r.reconciliation_id,))
        return None
    current_authority = current_observation = None
    current_refs = (runtime.before.snapshot_id,)
    checks = r.checks
    reason = r.outcome.value
    control = Control.PASS
    if r.outcome == Outcome.RECONCILIATION_FAILED:
        decision = Decision.DO_NOT_PROJECT
        checks += (check("FINAL_READ", None, (r.reconciliation_id,), "NOT_EVALUATED: failed reconciliation"),)
    elif r.outcome != Outcome.RECONCILED_SUCCESS:
        decision = Decision.HOLD_PROJECTION
        checks += (check("FINAL_READ", None, (r.reconciliation_id,), "NOT_EVALUATED: non-success reconciliation"),)
    else:
        runtime.inject("final")
        control, fresh_checks, observed, snapshot = runtime.fresh(final=True)
        checks += fresh_checks
        if observed:
            current_observation = observed.observation_version
            current_refs += (observed.snapshot_id,)
        if snapshot:
            current_authority = snapshot.authority_version
            current_refs += (snapshot.snapshot_id,)
        if control in (Control.FAIL_NONRETRYABLE, Control.HUMAN_AUTHORIZATION_REQUIRED):
            decision = Decision.DO_NOT_PROJECT
        elif control != Control.PASS:
            decision = Decision.HOLD_PROJECTION
        else:
            decision = Decision.PROJECT
        reason = control.value
    fault = runtime.faults.publication_fault
    failed = decision == Decision.PROJECT and fault in ("write", "event", "publication")
    if failed:
        decision = Decision.DO_NOT_PROJECT
        reason = "PUBLICATION_FAILED"
    applied = decision == Decision.PROJECT
    unavailable = failed and fault == "event"
    record = ProjectionDecision(
        **j.common("PROJECTOR"), projection_id=j.new_id("projection"),
        transition_id=e.transition_id, reconciliation_id=r.reconciliation_id,
        commit_id=commit.commit_id, object_id=e.object_id,
        plan_ref=commit.execution_plan_id, envelope_ref=e.envelope_id,
        definition_ref=e.definition_ref, initial_and_current_snapshot_refs=current_refs,
        expected_authority_version=e.source_authority_version,
        current_authority_version_or_null=current_authority,
        reconciled_observation_version=r.observed_version,
        current_observation_version_or_null=current_observation,
        action_interval_ref=r.action_interval_ref, target_state=e.target_state,
        authority_evidence_refs=e.authority_evidence_refs, checks=checks,
        final_decision=decision, reason_codes=(reason,), reasons=(reason,),
        write_outcome="FAILED" if failed else "APPLIED" if applied else "NOT_ATTEMPTED",
        authoritative_state_changed=applied,
        projected_authority_version_or_null=j.aggregate.authority_version + 1 if applied else None,
        retention_ref=retention, journal_record_status="UNAVAILABLE" if unavailable else "RECORDED",
    )
    event = None
    if not unavailable:
        events = j.aggregate.events
        event = RuntimeEvent(
            **j.common("EVENT_JOURNAL"), event_id=j.new_id("event"),
            event_type="StateProjected" if applied else
            "TransitionHeld" if decision == Decision.HOLD_PROJECTION else "TransitionRefused",
            sequence=len(events) + 1, causation_id_or_null=events[-1].event_id,
            actor_or_component="PROJECTOR", object_id=e.object_id,
            transition_id_or_null=e.transition_id, commit_id_or_null=commit.commit_id,
            source_authority_version_or_null=e.source_authority_version,
            observed_version_or_null=r.observed_version,
            artifact_refs=(record.projection_id, r.reconciliation_id, retention),
            outcome=decision.value, reason_codes=(reason,), visibility="INTERNAL_BOUNDED_TRACE",
            attempt_id_or_null=runtime.supervisor.current.attempt_id,
            parent_transition_id_or_null=e.transition_id,
            attempt_number_or_null=runtime.supervisor.current.attempt_number,
            prior_attempt_id_or_null=runtime.supervisor.current.prior_attempt_id,
            retry_policy_ref_or_null=runtime.policy.policy_id if runtime.policy else None,
            control_payload_or_null=None,
        )
    # Failure injection is evaluated before aggregate replacement; negative fallback uses the slot.
    j.publish(record, event, e.target_state if applied else None)
    if not applied:
        runtime.stop(Control.HOLD_AMBIGUOUS if decision == Decision.HOLD_PROJECTION
                     else Control.FAIL_NONRETRYABLE, reason, (record.projection_id,))
    return record
