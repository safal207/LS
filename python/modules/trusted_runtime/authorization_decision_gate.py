"""Deterministic fail-closed Authorization Decision Gate for LS."""
from __future__ import annotations

from typing import Iterable

from .authorization_contract import (
    AUTHORIZATION_GATE_POLICY_VERSION,
    ApprovalState,
    AuthorityState,
    AuthorizationDecision,
    AuthorizationReason,
    AuthorizationRequest,
    AuthorizationResult,
    CapabilityState,
    ContextState,
    PolicyEffect,
    digest,
)
from .continuity_coordinator import ContinuityDecision
from .roles_permissions_contract import AUTHORIZING_BASES, AuthorityBasis

AUTHORITY_BLOCK = {
    AuthorityState.DENIED: AuthorizationReason.AUTHORITY_DENIED,
    AuthorityState.REVOKED: AuthorizationReason.AUTHORITY_REVOKED,
    AuthorityState.EXPIRED: AuthorizationReason.AUTHORITY_EXPIRED,
    AuthorityState.RETIRED: AuthorizationReason.AUTHORITY_RETIRED,
}
APPROVAL_BLOCK = {
    ApprovalState.DENIED: AuthorizationReason.APPROVAL_DENIED,
    ApprovalState.REVOKED: AuthorizationReason.APPROVAL_REVOKED,
    ApprovalState.EXPIRED: AuthorizationReason.APPROVAL_EXPIRED,
}
CAPABILITY_BLOCK = {
    CapabilityState.CONSTRAINED: AuthorizationReason.CAPABILITY_CONSTRAINED,
    CapabilityState.UNAVAILABLE: AuthorizationReason.CAPABILITY_UNAVAILABLE,
}


def evaluate_authorization(
    request: AuthorizationRequest,
    *,
    evaluated_at: str,
    evaluated_by: str = "runtime:authorization-decision-gate",
) -> AuthorizationResult:
    if not evaluated_at or not evaluated_by:
        raise ValueError("evaluated_at and evaluated_by are required")
    reasons = _block_reasons(request)
    if reasons:
        decision = AuthorizationDecision.BLOCK
    else:
        reasons = _escalation_reasons(request)
        decision = (
            AuthorizationDecision.ESCALATE
            if reasons
            else AuthorizationDecision.ALLOW
        )
        if decision is AuthorizationDecision.ALLOW:
            reasons = _allow_reasons(request)
    identity = {
        "request_digest": request.request_digest,
        "decision": decision.value,
        "reason_codes": [item.value for item in reasons],
        "policy_version": AUTHORIZATION_GATE_POLICY_VERSION,
    }
    return AuthorizationResult(
        decision_id="authorization-decision:sha256:" + digest(identity),
        request_id=request.request_id,
        request_digest=request.request_digest,
        decision=decision,
        reason_codes=reasons,
        action_authorized=decision is AuthorizationDecision.ALLOW,
        evaluated_at=evaluated_at,
        evaluated_by=evaluated_by,
        metadata={
            "decision_precedence": ["BLOCK", "ESCALATE", "ALLOW"],
            "decision_is_not_execution": True,
            "capability_is_not_permission": True,
            "permission_is_not_execution": True,
            "role_membership_is_not_authority": True,
            "approval_requirement_is_not_approval": True,
            "evidence_binding": {
                "capability_result_digest": request.capability.result_digest,
                "capability_subject_binding_ref": request.capability_subject_binding_ref,
                "authority_result_digest": request.authority.result_digest,
                "policy_digest": request.policy.policy_digest,
                "approval_digest": request.approval.approval_digest,
                "context_digest": request.context.context_digest,
            },
        },
    )


def _block_reasons(request: AuthorizationRequest) -> tuple[AuthorizationReason, ...]:
    reasons: list[AuthorizationReason] = []
    if _subject_mismatch(request):
        reasons.append(AuthorizationReason.SUBJECT_MISMATCH)
    if _scope_matches(
        request,
        request.policy.action,
        request.policy.resource,
        request.policy.scope_ref,
    ) and request.policy.effect is PolicyEffect.DENY:
        reasons.append(AuthorizationReason.POLICY_DENIED)
    if request.capability.capability_id == request.required_capability_id:
        if (
            request.capability.assessment_decision
            is ContinuityDecision.BLOCK_FALSE_PRESENCE
        ):
            reasons.append(AuthorizationReason.CAPABILITY_EVIDENCE_BLOCKED)
        _append_mapping(reasons, CAPABILITY_BLOCK, request.capability.state)
    authority_relevant = _scope_matches(
        request,
        request.authority.action,
        request.authority.resource,
        request.authority.scope_ref,
    )
    if authority_relevant:
        if (
            request.authority.assessment_decision
            is ContinuityDecision.BLOCK_FALSE_PRESENCE
        ):
            reasons.append(AuthorizationReason.AUTHORITY_EVIDENCE_BLOCKED)
        _append_mapping(reasons, AUTHORITY_BLOCK, request.authority.state)
    approval_relevant = _scope_matches(
        request,
        request.approval.action,
        request.approval.resource,
        request.approval.scope_ref,
    )
    if approval_relevant:
        _append_mapping(reasons, APPROVAL_BLOCK, request.approval.state)
    return _unique(reasons)


def _escalation_reasons(request: AuthorizationRequest) -> tuple[AuthorizationReason, ...]:
    reasons: list[AuthorizationReason] = []
    cap, auth = request.capability, request.authority
    policy, approval, context = request.policy, request.approval, request.context

    if not request.capability_subject_binding_ref:
        reasons.append(AuthorizationReason.CAPABILITY_SUBJECT_BINDING_MISSING)
    if cap.assessment_decision is not ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION:
        reasons.append(AuthorizationReason.CAPABILITY_UNVERIFIED)
    if cap.state is CapabilityState.DISPUTED:
        reasons.append(AuthorizationReason.CAPABILITY_DISPUTED)
    elif cap.state not in {CapabilityState.AVAILABLE, CapabilityState.RECOVERED}:
        reasons.append(AuthorizationReason.CAPABILITY_UNKNOWN)
    if cap.capability_id != request.required_capability_id:
        reasons.append(AuthorizationReason.CAPABILITY_MISMATCH)
    if not cap.evidence_refs or not cap.context_refs:
        reasons.append(AuthorizationReason.CAPABILITY_UNVERIFIED)

    if auth.assessment_decision is not ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION:
        reasons.append(AuthorizationReason.AUTHORITY_UNVERIFIED)
    auth_state_reasons = {
        AuthorityState.PENDING_APPROVAL: AuthorizationReason.AUTHORITY_PENDING_APPROVAL,
        AuthorityState.SUSPENDED: AuthorizationReason.AUTHORITY_SUSPENDED,
        AuthorityState.DISPUTED: AuthorizationReason.AUTHORITY_DISPUTED,
    }
    if auth.state in auth_state_reasons:
        reasons.append(auth_state_reasons[auth.state])
    elif auth.state is not AuthorityState.ACTIVE:
        reasons.append(AuthorizationReason.AUTHORITY_UNKNOWN)
    if auth.basis not in AUTHORIZING_BASES:
        reasons.append(AuthorizationReason.AUTHORITY_BASIS_INSUFFICIENT)
    if not _scope_matches(request, auth.action, auth.resource, auth.scope_ref):
        reasons.append(AuthorizationReason.AUTHORITY_SCOPE_MISMATCH)
    if not auth.evidence_refs or not auth.provenance_refs:
        reasons.append(AuthorizationReason.AUTHORITY_PROVENANCE_MISSING)

    if policy.effect is PolicyEffect.UNKNOWN or not policy.evidence_refs:
        reasons.append(AuthorizationReason.POLICY_UNKNOWN)
    if not _scope_matches(request, policy.action, policy.resource, policy.scope_ref):
        reasons.append(AuthorizationReason.POLICY_SCOPE_MISMATCH)

    required = (
        policy.effect is PolicyEffect.REQUIRE_APPROVAL
        or auth.basis is AuthorityBasis.APPROVAL
    )
    if required and approval.state is not ApprovalState.VERIFIED:
        reasons.append(
            AuthorizationReason.APPROVAL_PENDING
            if approval.state is ApprovalState.PENDING
            else AuthorizationReason.APPROVAL_REQUIRED
            if approval.state is ApprovalState.NOT_REQUIRED
            else AuthorizationReason.APPROVAL_UNKNOWN
        )
    elif not required and approval.state in {
        ApprovalState.PENDING,
        ApprovalState.UNKNOWN,
    }:
        reasons.append(
            AuthorizationReason.APPROVAL_PENDING
            if approval.state is ApprovalState.PENDING
            else AuthorizationReason.APPROVAL_UNKNOWN
        )
    if approval.state is ApprovalState.VERIFIED:
        if not _scope_matches(
            request,
            approval.action,
            approval.resource,
            approval.scope_ref,
        ):
            reasons.append(AuthorizationReason.APPROVAL_SCOPE_MISMATCH)
        if not approval.approver_refs or not approval.evidence_refs:
            reasons.append(AuthorizationReason.APPROVAL_UNKNOWN)
        if (
            auth.basis is AuthorityBasis.APPROVAL
            and approval.approval_id not in auth.approval_refs
        ):
            reasons.append(AuthorizationReason.APPROVAL_REFERENCE_MISMATCH)

    if context.state is ContextState.STALE:
        reasons.append(AuthorizationReason.CONTEXT_STALE)
    elif context.state is ContextState.UNKNOWN or not context.evidence_refs:
        reasons.append(AuthorizationReason.CONTEXT_UNKNOWN)
    if not _scope_matches(
        request,
        context.action,
        context.resource,
        context.scope_ref,
    ):
        reasons.append(AuthorizationReason.CONTEXT_SCOPE_MISMATCH)
    if context.age_seconds > context.max_age_seconds:
        reasons.append(AuthorizationReason.CONTEXT_TOO_OLD)
    return _unique(reasons)


def _allow_reasons(request: AuthorizationRequest) -> tuple[AuthorizationReason, ...]:
    return (
        AuthorizationReason.CAPABILITY_VERIFIED,
        AuthorizationReason.AUTHORITY_VERIFIED,
        AuthorizationReason.POLICY_ALLOWED,
        AuthorizationReason.APPROVAL_VERIFIED
        if request.approval.state is ApprovalState.VERIFIED
        else AuthorizationReason.APPROVAL_NOT_REQUIRED,
        AuthorizationReason.CONTEXT_FRESH,
    )


def _subject_mismatch(request: AuthorizationRequest) -> bool:
    return any(
        value != request.subject_id
        for value in (
            request.capability.subject_id,
            request.authority.subject_id,
            request.approval.subject_id,
            request.context.subject_id,
        )
    )


def _scope_matches(
    request: AuthorizationRequest,
    action: str,
    resource: str,
    scope_ref: str,
) -> bool:
    return (action, resource, scope_ref) == (
        request.action,
        request.resource,
        request.scope_ref,
    )


def _append_mapping(
    reasons: list[AuthorizationReason],
    mapping: dict[object, AuthorizationReason],
    key: object,
) -> None:
    reason = mapping.get(key)
    if reason is not None:
        reasons.append(reason)


def _unique(reasons: Iterable[AuthorizationReason]) -> tuple[AuthorizationReason, ...]:
    return tuple(dict.fromkeys(reasons))


__all__ = ["evaluate_authorization"]
