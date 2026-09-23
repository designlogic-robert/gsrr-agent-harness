"""Deterministic local governance. Selection, validity and authority stay separate."""
from dataclasses import replace
from .contracts import (
    Check, Gate, Control, Mode, FixedInput, Step, Definition, AuthorityEvidence,
    CapabilityDescriptor, ExecutionEnvelope, ExecutionPlan, PlanValidationResult,
)
from .journal import Journal

PROFILE = "sufficiency-profile-1"


def check(rule: str, ok: bool | None, refs: tuple[str, ...], reason: str) -> Check:
    return Check(rule, refs, "UNRESOLVED" if ok is None else "PASS" if ok else "FAIL", reason)


def grant_check(grant: AuthorityEvidence | None, definition: Definition,
                source_version: int, subject_ref: str, plan_ref: str | None = None
                ) -> tuple[Control, tuple[Check, ...]]:
    if grant is None:
        return Control.FAIL_NONRETRYABLE, (check("AUTHORITY", False, (), "required grant absent"),)
    refs = (grant.evidence_id,)
    if grant.active is None:
        return Control.HOLD_AMBIGUOUS, (check("AUTHORITY", None, refs, "grant activity unknown"),)
    valid = (
        grant.active is True and grant.issuer_id == "fixture-issuer"
        and grant.actor_id == "USER-001" and grant.object_id == definition.object_id
        and grant.capability == definition.capability_id
        and grant.implementation_id == definition.implementation_id
        and type(grant.definition_version) is int
        and grant.definition_version == definition.definition_version
        and type(grant.source_authority_version) is int
        and grant.source_authority_version == source_version
        and grant.scope == "DOC-001:DRAFT:REVIEW"
    )
    if not valid:
        return Control.FAIL_NONRETRYABLE, (check("AUTHORITY", False, refs, "invalid scoped grant"),)
    if grant.human_required:
        expected = plan_ref if grant.subject_ref and ":plan:" in grant.subject_ref else subject_ref
        approved = (
            grant.subject_ref == expected and grant.decision == "APPROVE"
            and grant.human_issuer == "fixture-human-issuer" and bool(grant.policy_ref)
        )
        if not approved:
            return Control.HUMAN_AUTHORIZATION_REQUIRED, (
                check("HUMAN_SUBJECT", False, refs, "exact immutable subject authorization required"),
            )
    return Control.PASS, (check("AUTHORITY", True, refs, "active exact scoped evidence"),)


def descriptor(journal: Journal, d: Definition) -> CapabilityDescriptor:
    record = CapabilityDescriptor(
        **journal.common("CAPABILITY_REGISTRY"), descriptor_id="descriptor-1",
        capability_id=d.capability_id, implementation_id=d.implementation_id,
        descriptor_version=1, input_contract_ref="fixed-input-contract",
        expected_effects=d.required_effects, forbidden_effects=d.forbidden_effects,
        authority_requirements="authority-contract", idempotency_posture="RUN_LOCAL_ONCE",
        fixture_boundary_ref="fixture-boundary",
        action_observation_contract_ref="action-observation-contract",
        supported_realization_modes=(Mode.EXPLICIT_PLAN, Mode.DELEGATED_REALIZATION),
        owns_internal_planning_by_mode=((Mode.EXPLICIT_PLAN, False), (Mode.DELEGATED_REALIZATION, True)),
        supports_reconciliation_evidence=True,
    )
    return journal.retain(record.descriptor_id, record)


def envelope(journal, approval, transition, d, before, observed):
    refs = (approval.approval_id, transition.transition_id, before.snapshot_id, observed.snapshot_id)
    checks = (check("ENVELOPE_DERIVATION", (
        approval.disposition == Gate.PASS and transition.target_state == d.target_state
        and approval.transition_id == transition.transition_id
        and approval.source_authority_version == before.authority_version
        and approval.source_observation_version == observed.observation_version
    ), refs, "recompute complete bounds from original approval and fixture"),)
    if any(c.result != "PASS" for c in checks):
        raise ValueError("invalid envelope derivation")
    e = ExecutionEnvelope(
        **journal.common("GSRR_SLICE_01"), envelope_id=journal.new_id("envelope"),
        approval_id=approval.approval_id, transition_id=transition.transition_id,
        object_id=d.object_id, source_state=d.source_state, target_state=d.target_state,
        source_authority_version=before.authority_version,
        source_observation_version=observed.observation_version,
        definition_ref=d.definition_id, authority_evidence_refs=approval.authority_evidence_refs,
        required_effects=d.required_effects, forbidden_effects=d.forbidden_effects,
        required_capability=d.capability_id, allowed_implementation_ids=(d.implementation_id,),
        postconditions=d.postconditions, reconciliation_requirements=d.evidence_rules,
        execution_constraints=d.constraints, envelope_check_results=checks,
        fixture_boundary_ref="fixture-boundary",
    )
    return journal.retain(e.envelope_id, e)


class ExplicitPlanner:
    def __init__(self):
        self.calls = 0

    def propose(self, journal, e, attempt_id, defect=""):
        self.calls += 1
        return build_instruction(journal, e, attempt_id, Mode.EXPLICIT_PLAN, defect)


def build_instruction(journal, e, attempt_id, mode, defect=""):
    if defect == "infeasible":
        return None
    fixed = FixedInput(e.object_id, e.source_state, e.target_state, e.source_observation_version)
    if defect == "target":
        fixed = replace(fixed, target_state="APPROVED")
    elif defect == "object":
        fixed = replace(fixed, object_id="OTHER")
    elif defect == "source":
        fixed = replace(fixed, expected_observation_version=True)
    step = Step(e.required_capability, e.allowed_implementation_ids[0], fixed)
    if defect == "implementation":
        step = replace(step, implementation_id="unregistered")
    p = ExecutionPlan(
        **journal.common("PLANNER" if mode == Mode.EXPLICIT_PLAN else "GSRR_SLICE_01"),
        plan_id=journal.new_id("plan"), envelope_id=e.envelope_id,
        transition_id=e.transition_id, object_id=e.object_id,
        source_authority_version=e.source_authority_version,
        source_observation_version=e.source_observation_version,
        steps=(step,) if defect != "extra_step" else (step, step),
        accepted_envelope_obligations_ref="" if defect == "obligations" else e.envelope_id,
        sufficiency_policy_ref=PROFILE,
        unresolved_fields=("obligations",) if defect == "obligations" else (),
        attempt_id=attempt_id, realization_mode=mode,
    )
    return journal.retain(p.plan_id, p)


def validate_plan(journal, p, e, approval, d, cap, attempt_id):
    refs = (p.plan_id, e.envelope_id, approval.approval_id, cap.descriptor_id)
    missing = bool(p.unresolved_fields) or not p.accepted_envelope_obligations_ref
    expected = Step(d.capability_id, d.implementation_id, FixedInput(
        e.object_id, e.source_state, e.target_state, e.source_observation_version))
    exact = (
        journal.get(p.plan_id) == p
        and journal.get(e.envelope_id) == e
        and journal.get(approval.approval_id) == approval
        and journal.get(cap.descriptor_id) == cap
        and type(p.steps) is tuple and len(p.steps) == 1 and p.steps[0] == expected
        and type(p.steps[0].fixed_input.expected_observation_version) is int
        and p.envelope_id == e.envelope_id and p.transition_id == e.transition_id
        and p.object_id == e.object_id and p.attempt_id == attempt_id
        and p.source_authority_version == e.source_authority_version
        and p.source_observation_version == e.source_observation_version
        and p.accepted_envelope_obligations_ref == e.envelope_id
        and p.sufficiency_policy_ref == PROFILE
        and p.realization_mode in cap.supported_realization_modes
        and cap.implementation_id in e.allowed_implementation_ids
        and cap.capability_id == e.required_capability == d.capability_id
        and cap.input_contract_ref == "fixed-input-contract"
        and cap.authority_requirements == "authority-contract"
        and cap.idempotency_posture == "RUN_LOCAL_ONCE"
        and cap.action_observation_contract_ref == "action-observation-contract"
        and cap.expected_effects == e.required_effects
        and cap.forbidden_effects == e.forbidden_effects
        and cap.supports_reconciliation_evidence is True
        and cap.owns_internal_planning_by_mode == (
            (Mode.EXPLICIT_PLAN, False), (Mode.DELEGATED_REALIZATION, True))
        and cap.fixture_boundary_ref == e.fixture_boundary_ref == "fixture-boundary"
        and e.required_effects == d.required_effects and e.forbidden_effects == d.forbidden_effects
        and e.postconditions == d.postconditions and e.reconciliation_requirements == d.evidence_rules
        and e.execution_constraints == d.constraints and approval.disposition == Gate.PASS
    )
    disposition = Gate.HELD if missing else Gate.PASS if exact else Gate.REFUSED
    c = check("PLAN_ENVELOPE", None if missing else exact, refs,
              "missing complete obligations" if missing else "exact immutable capability contract")
    v = PlanValidationResult(
        **journal.common("DASA"), plan_validation_id=journal.new_id("plan-validation"),
        plan_id=p.plan_id, envelope_id=e.envelope_id, approval_id=approval.approval_id,
        checked_authority_version=e.source_authority_version,
        checked_observation_version=e.source_observation_version,
        authority_evidence_refs=e.authority_evidence_refs, check_results=(c,),
        disposition=disposition, reasons=(c.reason,), attempt_id=attempt_id,
    )
    return journal.retain(v.plan_validation_id, v)
