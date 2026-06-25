"""Governed Roles/Permissions Track Center for LS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .continuity_coordinator import (
    ContinuityAssessment,
    EntityStatus,
    TrackObservation,
    assess_track_observation,
)
from .roles_permissions_contract import (
    AUTHORIZING_BASES,
    CURRENT_CLAIM_TYPES,
    LESSON_TYPES,
    ROLES_PERMISSIONS_TRACK,
    AuthorityBasis,
    AuthorityStatus,
    RolePermissionEvent,
    RolePermissionEventType,
    digest,
)

ROLE_PERMISSION_RESULT_VERSION = "trusted_runtime.role_permission_result.v0.1"
ROLE_PERMISSION_POLICY_VERSION = "roles_permissions_track_center.v0.1"

CLOSED_AUTHORITY_STATUSES = frozenset(
    {
        AuthorityStatus.DENIED,
        AuthorityStatus.REVOKED,
        AuthorityStatus.EXPIRED,
        AuthorityStatus.RETIRED,
    }
)
PAUSED_AUTHORITY_STATUSES = frozenset(
    {
        AuthorityStatus.PENDING_APPROVAL,
        AuthorityStatus.SUSPENDED,
        AuthorityStatus.DISPUTED,
    }
)


@dataclass(frozen=True)
class RolePermissionResult:
    result_id: str
    event: RolePermissionEvent
    observation: TrackObservation
    assessment: ContinuityAssessment
    processed_at: str
    processed_by: str = "runtime:roles-permissions-track-center"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = ROLE_PERMISSION_POLICY_VERSION
    schema_version: str = ROLE_PERMISSION_RESULT_VERSION

    def __post_init__(self) -> None:
        if not all((self.result_id, self.processed_at, self.processed_by)):
            raise ValueError("role permission result fields must not be empty")
        if self.schema_version != ROLE_PERMISSION_RESULT_VERSION:
            raise ValueError(f"unsupported role permission result: {self.schema_version}")
        if self.event.authority_id != self.observation.subject_id:
            raise ValueError("authority event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("authority observation and assessment mismatch")
        if self.observation.track != ROLES_PERMISSIONS_TRACK:
            raise ValueError("role permission result requires canonical track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "role_registry_mutation_allowed": False,
            "permission_registry_mutation_allowed": False,
            "access_grant_allowed": False,
            "access_denial_allowed": False,
            "approval_allowed": False,
            "delegation_allowed": False,
            "policy_mutation_allowed": False,
            "work_scheduling_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_role_permission_observation(event: RolePermissionEvent) -> TrackObservation:
    candidate = event.event_type in LESSON_TYPES
    observation_id = "role-permission-observation:sha256:" + digest(
        {
            "event_id": event.event_id,
            "event_digest": event.event_digest,
            "track": ROLES_PERMISSIONS_TRACK,
            "policy_version": ROLE_PERMISSION_POLICY_VERSION,
        }
    )
    return TrackObservation(
        observation_id=observation_id,
        track=ROLES_PERMISSIONS_TRACK,
        subject_id=event.authority_id,
        entity_status=_entity_status(event),
        knowledge_class=event.knowledge_class,
        statement=event.statement,
        occurred_at=event.occurred_at,
        confidence=event.confidence,
        evidence_refs=event.evidence_refs,
        claims_current_presence=event.event_type in CURRENT_CLAIM_TYPES,
        identity_candidate_statement=(
            event.identity_candidate_statement if candidate else None
        ),
        identity_scope=event.identity_scope if candidate else None,
        identity_repeat_key=event.identity_repeat_key if candidate else None,
        metadata={
            "authority_id": event.authority_id,
            "subject_id": event.subject_id,
            "authority_event_id": event.event_id,
            "authority_event_digest": event.event_digest,
            "authority_event_type": event.event_type.value,
            "authority_status": event.authority_status.value,
            "authority_basis": event.authority_basis.value,
            "action": event.action,
            "resource": event.resource,
            "scope_ref": event.scope_ref,
            "repeat_count": event.repeat_count,
            "provenance_refs": list(event.provenance_refs),
            "context_refs": list(event.context_refs),
            "observer_refs": list(event.observer_refs),
            "role_refs": list(event.role_refs),
            "approval_refs": list(event.approval_refs),
            "capability_is_not_permission": True,
            "role_is_not_action_authorization": True,
            "permission_is_not_delegation": True,
            "current_authority_requires_scope_and_provenance": True,
            "track_center_policy_version": ROLE_PERMISSION_POLICY_VERSION,
        },
    )


def process_role_permission_event(
    event: RolePermissionEvent,
    *,
    processed_at: str,
    processed_by: str = "runtime:roles-permissions-track-center",
) -> RolePermissionResult:
    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")
    observation = build_role_permission_observation(event)
    assessment = assess_track_observation(
        observation,
        assessed_at=processed_at,
        assessed_by="runtime:continuity-coordinator",
    )
    result_id = "role-permission-result:sha256:" + digest(
        {
            "event_digest": event.event_digest,
            "observation_digest": observation.observation_digest,
            "assessment_id": assessment.assessment_id,
            "policy_version": ROLE_PERMISSION_POLICY_VERSION,
        }
    )
    return RolePermissionResult(
        result_id=result_id,
        event=event,
        observation=observation,
        assessment=assessment,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "handoff": (
                "role_permission_event -> track_observation -> continuity_assessment"
            ),
            "role_assignment_does_not_authorize_action": True,
            "approval_requirement_is_not_approval": True,
            "revoked_authority_cannot_reappear_as_current": True,
            "single_event_cannot_modify_stable_identity": True,
            "authorization_decision": "separate_governed_operation",
        },
    )


def _entity_status(event: RolePermissionEvent) -> EntityStatus:
    if event.event_type in CURRENT_CLAIM_TYPES:
        if event.authority_status in CLOSED_AUTHORITY_STATUSES:
            return EntityStatus.CLOSED
        if event.authority_status in PAUSED_AUTHORITY_STATUSES:
            return EntityStatus.PAUSED
        if event.authority_status is not AuthorityStatus.ACTIVE:
            return EntityStatus.UNKNOWN
        if event.authority_basis not in AUTHORIZING_BASES:
            return EntityStatus.UNKNOWN
        if not all((event.action, event.resource, event.scope_ref)):
            return EntityStatus.UNKNOWN
        if not event.evidence_refs or not event.provenance_refs or not event.context_refs:
            return EntityStatus.UNKNOWN
        if event.authority_basis is AuthorityBasis.APPROVAL and not event.approval_refs:
            return EntityStatus.UNKNOWN
        return EntityStatus.ACTIVE

    if event.authority_status is AuthorityStatus.ACTIVE:
        return EntityStatus.ACTIVE
    if event.authority_status in PAUSED_AUTHORITY_STATUSES:
        return EntityStatus.PAUSED
    if event.authority_status in CLOSED_AUTHORITY_STATUSES:
        return EntityStatus.CLOSED
    return EntityStatus.UNKNOWN


__all__ = [
    "ROLES_PERMISSIONS_TRACK",
    "AuthorityBasis",
    "AuthorityStatus",
    "RolePermissionEvent",
    "RolePermissionEventType",
    "RolePermissionResult",
    "process_role_permission_event",
]
