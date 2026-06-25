"""Adapters from governed LS track results to authorization evidence."""
from __future__ import annotations

from .authorization_contract import (
    AuthorityEvidence,
    AuthorityState,
    CapabilityEvidence,
    CapabilityState,
    digest,
)
from .capabilities_constraints_track_center import CapabilityConstraintResult
from .roles_permissions_track_center import RolePermissionResult


def capability_evidence_from_result(
    result: CapabilityConstraintResult,
    *,
    subject_id: str,
    subject_binding_ref: str,
) -> CapabilityEvidence:
    """Bind a capability result to a subject using separate provenance."""
    if not subject_id or not subject_binding_ref:
        raise ValueError("subject_id and subject_binding_ref are required")
    return CapabilityEvidence(
        result_id=result.result_id,
        assessment_id=result.assessment.assessment_id,
        assessment_decision=result.assessment.decision,
        subject_id=subject_id,
        capability_id=result.event.capability_id,
        state=_capability_state(result.event.capability_status.value),
        evidence_refs=result.event.evidence_refs,
        context_refs=result.event.context_refs,
        result_digest=digest(result.to_dict()),
    )


def authority_evidence_from_result(
    result: RolePermissionResult,
) -> AuthorityEvidence:
    """Preserve the role/permission result's scoped subject and provenance."""
    event = result.event
    return AuthorityEvidence(
        result_id=result.result_id,
        assessment_id=result.assessment.assessment_id,
        assessment_decision=result.assessment.decision,
        subject_id=event.subject_id,
        authority_id=event.authority_id,
        state=_authority_state(event.authority_status.value),
        basis=event.authority_basis,
        action=event.action,
        resource=event.resource,
        scope_ref=event.scope_ref,
        evidence_refs=event.evidence_refs,
        provenance_refs=event.provenance_refs,
        approval_refs=event.approval_refs,
        result_digest=digest(result.to_dict()),
    )


def _capability_state(value: str) -> CapabilityState:
    return CapabilityState._value2member_map_.get(value, CapabilityState.UNKNOWN)


def _authority_state(value: str) -> AuthorityState:
    return AuthorityState._value2member_map_.get(value, AuthorityState.UNKNOWN)


__all__ = [
    "authority_evidence_from_result",
    "capability_evidence_from_result",
]
