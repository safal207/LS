from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.authorization_contract import (
    ApprovalEvidence,
    ApprovalState,
    AuthorityEvidence,
    AuthorityState,
    AuthorizationDecision,
    AuthorizationReason,
    AuthorizationRequest,
    CapabilityEvidence,
    CapabilityState,
    ContextState,
    ExecutionContextEvidence,
    PolicyEffect,
    PolicyEvidence,
)
from trusted_runtime.authorization_decision_gate import evaluate_authorization
from trusted_runtime.continuity_coordinator import ContinuityDecision
from trusted_runtime.roles_permissions_contract import AuthorityBasis

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/authorization_result.schema.json"
SUBJECT = "agent:release-bot"
ACTION = "deploy"
RESOURCE = "service:payments"
SCOPE = "scope:production"
CAPABILITY = "capability:deploy-service"


def _request() -> AuthorizationRequest:
    return AuthorizationRequest(
        request_id="authorization-request:1",
        subject_id=SUBJECT,
        intent_ref="intent:release:42",
        action=ACTION,
        resource=RESOURCE,
        scope_ref=SCOPE,
        required_capability_id=CAPABILITY,
        capability=CapabilityEvidence(
            result_id="capability-result:1",
            assessment_id="capability-assessment:1",
            assessment_decision=ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION,
            subject_id=SUBJECT,
            capability_id=CAPABILITY,
            state=CapabilityState.AVAILABLE,
            evidence_refs=("evidence:capability",),
            context_refs=("context:production",),
            result_digest="a" * 64,
        ),
        authority=AuthorityEvidence(
            result_id="authority-result:1",
            assessment_id="authority-assessment:1",
            assessment_decision=ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION,
            subject_id=SUBJECT,
            authority_id="authority:deploy-production",
            state=AuthorityState.ACTIVE,
            basis=AuthorityBasis.DIRECT_PERMISSION,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            evidence_refs=("evidence:authority",),
            provenance_refs=("provenance:policy",),
            approval_refs=(),
            result_digest="b" * 64,
        ),
        policy=PolicyEvidence(
            policy_id="policy:production-deploy",
            policy_version="2026-06-25",
            effect=PolicyEffect.ALLOW,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            evidence_refs=("evidence:policy",),
            policy_digest="c" * 64,
        ),
        approval=ApprovalEvidence(
            approval_id="approval:not-required",
            subject_id=SUBJECT,
            state=ApprovalState.NOT_REQUIRED,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            approver_refs=(),
            evidence_refs=(),
            approval_digest="d" * 64,
        ),
        context=ExecutionContextEvidence(
            context_id="execution-context:1",
            subject_id=SUBJECT,
            state=ContextState.FRESH,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            age_seconds=15,
            max_age_seconds=60,
            evidence_refs=("evidence:context",),
            context_digest="e" * 64,
        ),
        requested_at="2026-06-25T12:00:00Z",
    )


def _evaluate(request: AuthorizationRequest):
    return evaluate_authorization(
        request,
        evaluated_at="2026-06-25T12:00:01Z",
    )


def test_verified_scoped_evidence_allows_action_but_does_not_execute() -> None:
    result = _evaluate(_request())
    assert result.decision is AuthorizationDecision.ALLOW
    assert result.action_authorized is True
    assert result.reason_codes == (
        AuthorizationReason.CAPABILITY_VERIFIED,
        AuthorizationReason.AUTHORITY_VERIFIED,
        AuthorizationReason.POLICY_ALLOWED,
        AuthorizationReason.APPROVAL_NOT_REQUIRED,
        AuthorizationReason.CONTEXT_FRESH,
    )
    assert result.to_dict()["execution_authorized"] is False


def test_required_verified_approval_allows() -> None:
    request = _request()
    request = replace(
        request,
        policy=replace(request.policy, effect=PolicyEffect.REQUIRE_APPROVAL),
        authority=replace(
            request.authority,
            basis=AuthorityBasis.APPROVAL,
            approval_refs=("approval:change-board:42",),
        ),
        approval=replace(
            request.approval,
            approval_id="approval:change-board:42",
            state=ApprovalState.VERIFIED,
            approver_refs=("approver:change-board",),
            evidence_refs=("evidence:approval",),
        ),
    )
    result = _evaluate(request)
    assert result.decision is AuthorizationDecision.ALLOW
    assert AuthorizationReason.APPROVAL_VERIFIED in result.reason_codes


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (AuthorityState.DENIED, AuthorizationReason.AUTHORITY_DENIED),
        (AuthorityState.REVOKED, AuthorizationReason.AUTHORITY_REVOKED),
        (AuthorityState.EXPIRED, AuthorizationReason.AUTHORITY_EXPIRED),
        (AuthorityState.RETIRED, AuthorizationReason.AUTHORITY_RETIRED),
    ],
)
def test_closed_authority_blocks(state: AuthorityState, reason: AuthorizationReason) -> None:
    request = _request()
    result = _evaluate(replace(request, authority=replace(request.authority, state=state)))
    assert result.decision is AuthorizationDecision.BLOCK
    assert reason in result.reason_codes
    assert result.action_authorized is False


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (ApprovalState.DENIED, AuthorizationReason.APPROVAL_DENIED),
        (ApprovalState.REVOKED, AuthorizationReason.APPROVAL_REVOKED),
        (ApprovalState.EXPIRED, AuthorizationReason.APPROVAL_EXPIRED),
    ],
)
def test_negative_approval_blocks(state: ApprovalState, reason: AuthorizationReason) -> None:
    request = _request()
    result = _evaluate(replace(request, approval=replace(request.approval, state=state)))
    assert result.decision is AuthorizationDecision.BLOCK
    assert reason in result.reason_codes


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (CapabilityState.CONSTRAINED, AuthorizationReason.CAPABILITY_CONSTRAINED),
        (CapabilityState.UNAVAILABLE, AuthorizationReason.CAPABILITY_UNAVAILABLE),
    ],
)
def test_current_capability_failure_blocks(
    state: CapabilityState,
    reason: AuthorizationReason,
) -> None:
    request = _request()
    result = _evaluate(replace(request, capability=replace(request.capability, state=state)))
    assert result.decision is AuthorizationDecision.BLOCK
    assert reason in result.reason_codes


def test_policy_deny_has_precedence_over_uncertainty() -> None:
    request = _request()
    request = replace(
        request,
        policy=replace(request.policy, effect=PolicyEffect.DENY),
        context=replace(request.context, state=ContextState.STALE),
        authority=replace(request.authority, basis=AuthorityBasis.ROLE_ASSIGNMENT),
    )
    result = _evaluate(request)
    assert result.decision is AuthorizationDecision.BLOCK
    assert result.reason_codes == (AuthorizationReason.POLICY_DENIED,)


def test_cross_subject_evidence_blocks() -> None:
    request = _request()
    result = _evaluate(
        replace(
            request,
            authority=replace(request.authority, subject_id="agent:other"),
        )
    )
    assert result.decision is AuthorizationDecision.BLOCK
    assert AuthorizationReason.SUBJECT_MISMATCH in result.reason_codes


@pytest.mark.parametrize(
    ("request", "reason"),
    [
        (
            replace(
                _request(),
                authority=replace(
                    _request().authority,
                    basis=AuthorityBasis.ROLE_ASSIGNMENT,
                ),
            ),
            AuthorizationReason.AUTHORITY_BASIS_INSUFFICIENT,
        ),
        (
            replace(
                _request(),
                authority=replace(
                    _request().authority,
                    state=AuthorityState.PENDING_APPROVAL,
                ),
            ),
            AuthorizationReason.AUTHORITY_PENDING_APPROVAL,
        ),
        (
            replace(
                _request(),
                context=replace(_request().context, state=ContextState.STALE),
            ),
            AuthorizationReason.CONTEXT_STALE,
        ),
        (
            replace(
                _request(),
                context=replace(_request().context, age_seconds=61),
            ),
            AuthorizationReason.CONTEXT_TOO_OLD,
        ),
        (
            replace(
                _request(),
                capability=replace(
                    _request().capability,
                    assessment_decision=ContinuityDecision.HOLD_FOR_REVIEW,
                ),
            ),
            AuthorizationReason.CAPABILITY_UNVERIFIED,
        ),
        (
            replace(
                _request(),
                authority=replace(_request().authority, scope_ref="scope:staging"),
            ),
            AuthorizationReason.AUTHORITY_SCOPE_MISMATCH,
        ),
    ],
)
def test_uncertainty_escalates(
    request: AuthorizationRequest,
    reason: AuthorizationReason,
) -> None:
    result = _evaluate(request)
    assert result.decision is AuthorizationDecision.ESCALATE
    assert reason in result.reason_codes
    assert result.action_authorized is False


def test_required_pending_approval_escalates() -> None:
    request = _request()
    request = replace(
        request,
        policy=replace(request.policy, effect=PolicyEffect.REQUIRE_APPROVAL),
        approval=replace(request.approval, state=ApprovalState.PENDING),
    )
    result = _evaluate(request)
    assert result.decision is AuthorizationDecision.ESCALATE
    assert AuthorizationReason.APPROVAL_PENDING in result.reason_codes


def test_verified_approval_must_match_scope_and_have_provenance() -> None:
    request = _request()
    request = replace(
        request,
        policy=replace(request.policy, effect=PolicyEffect.REQUIRE_APPROVAL),
        approval=replace(
            request.approval,
            state=ApprovalState.VERIFIED,
            scope_ref="scope:staging",
        ),
    )
    result = _evaluate(request)
    assert result.decision is AuthorizationDecision.ESCALATE
    assert AuthorizationReason.APPROVAL_SCOPE_MISMATCH in result.reason_codes
    assert AuthorizationReason.APPROVAL_UNKNOWN in result.reason_codes


def test_result_is_deterministic_schema_valid_and_non_executing() -> None:
    first = _evaluate(_request())
    second = _evaluate(_request())
    assert first.decision_id == second.decision_id
    payload = first.to_dict()
    denied = (
        "capability_registry_mutation_allowed",
        "role_registry_mutation_allowed",
        "permission_registry_mutation_allowed",
        "approval_mutation_allowed",
        "policy_mutation_allowed",
        "context_mutation_allowed",
        "work_scheduling_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    )
    assert all(payload[field] is False for field in denied)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
