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


BLOCK_AUTHORITY_REASONS = {
    AuthorityState.DENIED: AuthorizationReason.AUTHORITY_DENIED,
    AuthorityState.REVOKED: AuthorizationReason.AUTHORITY_REVOKED,
    AuthorityState.EXPIRED: AuthorizationReason.AUTHORITY_EXPIRED,
    AuthorityState.RETIRED: AuthorizationReason.AUTHORITY_RETIRED,
}
BLOCK_APPROVAL_REASONS = {
    ApprovalState.DENIED: AuthorizationReason.APPROVAL_DENIED,
    ApprovalState.REVOKED: AuthorizationReason.APPROVAL_REVOKED,
    ApprovalState.EXPIRED: AuthorizationReason.APPROVAL_EXPIRED,
}
BLOCK_CAPABILITY_REASONS = {
    CapabilityState.CONSTRAINED: AuthorizationReason.CAPABILITY_CONSTRAINED,
    CapabilityState.UNAVAILABLE: AuthorizationReason.CAPABILITY_UNAVAILABLE,
}


def evaluate_authorization(
    request: AuthorizationRequest,
    *,
    evaluated_at: str,
    evaluated_by: str = "runtime:authorization-decision-gate",
) -> AuthorizationResult:
    """Evaluate one immutable authorization request without executing it."""
    if not evaluated_at or not evaluated_by:
        raise ValueError("evaluated_at and evaluated_by are required")

    blocked = _block_reasons(request)
    if blocked:
        decision = AuthorizationDecision.BLOCK
        reasons = blocked
    else:
        escalations = _escalation_reasons(request)
        if escalations:
            decision = AuthorizationDecision.ESCALATE
            reasons = escalations
        else:
            decision = AuthorizationDecision.ALLOW
            reasons = _allow_reasons(request)

    identity = {
        "request_digest": request.request_digest,
        "decision": decision.value,
        "reason_codes": [reason.value for reason in reasons],
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
                "authority_result_digest": request.authority.result_digest,
                "policy_digest": request.policy.policy_digest,
                "approval_digest": request.approval.approval_digest,
                "context_digest": request.context.context_digest,
            },
        },
    )


def _block_reasons(request: AuthorizationRequest) -> tuple[AuthorizationReason, ...]:
    reasons: list[AuthorizationReason] = []
    if request.policy.effect is PolicyEffect.DENY:
        reasons.append(AuthorizationReason.POLICY_DENIED)
    if request.capability.assessment_decision is ContinuityDecision.BLOCK_FALSE_PRESENCE:
        reasons.append(AuthorizationReason.CAPABILITY_EVIDENCE_BLOCKED)
    capability_reason = BLOCK_CAPABILITY_REASONS.get(request.capability.state)
    if capability_reason is not None:
        reasons.append(capability_reason)
    if request.authority.assessment_decision is ContinuityDecision.BLOCK_FALSE_PRESENCE:
        reasons.append(AuthorizationReason.AUTHORITY_EVIDENCE_BLOCKED)
    authority_reason = BLOCK_AUTHORITY_REASONS.get(request.authority.state)
    if authority_reason is not None:
        reasons.append(authority_reason)
    approval_reason = BLOCK_APPROVAL_REASONS.get(request.approval.state)
    if approval_reason is not None:
        reasons.append(approval_reason)
    if _subject_mismatch(request):
        reasons.append(AuthorizationReason.SUBJECT_MISMATCH)
    return _unique(reasons)


def _escalation_reasons(
    request: AuthorizationRequest,
) -> tuple[AuthorizationReason, ...]:
    reasons: list[AuthorizationReason] = []
    capability = request.capability
    authority = request.authority
    policy = request.policy
    approval = request.approval
    context = request.context

    if capability.assessment_decision is not ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION:
        reasons.append(AuthorizationReason.CAPABILITY_UNVERIFIED)
    if capability.state is CapabilityState.DISPUTED:
        reasons.append(AuthorizationReason.CAPABILITY_DISPUTED)
    elif capability.state not in {CapabilityState.AVAILABLE, CapabilityState.RECOVERED}:
        reasons.append(AuthorizationReason.CAPABILITY_UNKNOWN)
    if capability.capability_id != request.required_capability_id:
        reasons.append(AuthorizationReason.CAPABILITY_MISMATCH)
    if not capability.evidence_refs or not capability.context_refs:
        reasons.append(AuthorizationReason.CAPABILITY_UNVERIFIED)

    if authority.assessment_decision is not ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION:
        reasons.append(AuthorizationReason.AUTHORITY_UNVERIFIED)
    if authority.state is AuthorityState.PENDING_APPROVAL:
        reasons.append(AuthorizationReason.AUTHORITY_PENDING_APPROVAL)
    elif authority.state is AuthorityState.SUSPENDED:
        reasons.append(AuthorizationReason.AUTHORITY_SUSPENDED)
    elif authority.state is AuthorityState.DISPUTED:
        reasons.append(AuthorizationReason.AUTHORITY_DISPUTED)
    elif authority.state is not AuthorityState.ACTIVE:
        reasons.append(AuthorizationReason.AUTHORITY_UNKNOWN)
    if authority.basis not in AUTHORIZING_BASES:
        reasons.append(AuthorizationReason.AUTHORITY_BASIS_INSUFFICIENT)
    if not _scope_matches(
        request,
        authority.action,
        authority.resource,
        authority.scope_ref,
    ):
        reasons.append(AuthorizationReason.AUTHORITY_SCOPE_MISMATCH)
    if not authority.evidence_refs or not authority.provenance_refs:
        reasons.append(AuthorizationReason.AUTHORITY_PROVENANCE_MISSING)

    if policy.effect is PolicyEffect.UNKNOWN:
        reasons.append(AuthorizationReason.POLICY_UNKNOWN)
    if not _scope_matches(request, policy.action, policy.resource, policy.scope_ref):
        reasons.append(AuthorizationReason.POLICY_SCOPE_MISMATCH)
    if not policy.evidence_refs:
        reasons.append(AuthorizationReason.POLICY_UNKNOWN)

    approval_required = (
        policy.effect is PolicyEffect.REQUIRE_APPROVAL
        or authority.basis is AuthorityBasis.APPROVAL
    )
    if approval_required:
        if approval.state is ApprovalState.NOT_REQUIRED:
            reasons.append(AuthorizationReason.APPROVAL_REQUIRED)
        elif approval.state is ApprovalState.PENDING:
            reasons.append(AuthorizationReason.APPROVAL_PENDING)
        elif approval.state is ApprovalState.UNKNOWN:
            reasons.append(AuthorizationReason.APPROVAL_UNKNOWN)
        elif approval.state is not ApprovalState.VERIFIED:
            reasons.append(AuthorizationReason.APPROVAL_REQUIRED)
    elif approval.state is ApprovalState.PENDING:
        reasons.append(AuthorizationReason.APPROVAL_PENDING)
    elif approval.state is ApprovalState.UNKNOWN:
        reasons.append(AuthorizationReason.APPROVAL_UNKNOWN)

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

    if context.state is ContextState.STALE:
        reasons.append(AuthorizationReason.CONTEXT_STALE)
    elif context.state is ContextState.UNKNOWN:
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
    if not context.evidence_refs:
        reasons.append(AuthorizationReason.CONTEXT_UNKNOWN)

    return _unique(reasons)


def _allow_reasons(request: AuthorizationRequest) -> tuple[AuthorizationReason, ...]:
    approval_reason = (
        AuthorizationReason.APPROVAL_VERIFIED
        if request.approval.state is ApprovalState.VERIFIED
        else AuthorizationReason.APPROVAL_NOT_REQUIRED
    )
    return (
        AuthorizationReason.CAPABILITY_VERIFIED,
        AuthorizationReason.AUTHORITY_VERIFIED,
        AuthorizationReason.POLICY_ALLOWED,
        approval_reason,
        AuthorizationReason.CONTEXT_FRESH,
    )


def _subject_mismatch(request: AuthorizationRequest) -> bool:
    return any(
        subject_id != request.subject_id
        for subject_id in (
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
    return (
        action == request.action
        and resource == request.resource
        and scope_ref == request.scope_ref
    )


def _unique(
    reasons: Iterable[AuthorizationReason],
) -> tuple[AuthorizationReason, ...]:
    return tuple(dict.fromkeys(reasons))


__all__ = ["evaluate_authorization"]
