"""Versioned contracts for the LS Roles/Permissions Track Center."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from .continuity_coordinator import KnowledgeClass

ROLES_PERMISSIONS_TRACK = "roles.permissions"
ROLE_PERMISSION_EVENT_VERSION = "trusted_runtime.role_permission_event.v0.1"


class AuthorityStatus(str, Enum):
    OBSERVED = "OBSERVED"
    ACTIVE = "ACTIVE"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    DENIED = "DENIED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    DISPUTED = "DISPUTED"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class AuthorityBasis(str, Enum):
    NONE = "NONE"
    ROLE_ASSIGNMENT = "ROLE_ASSIGNMENT"
    DIRECT_PERMISSION = "DIRECT_PERMISSION"
    DELEGATION = "DELEGATION"
    APPROVAL = "APPROVAL"
    POLICY = "POLICY"
    UNKNOWN = "UNKNOWN"


class RolePermissionEventType(str, Enum):
    ROLE_OBSERVED = "ROLE_OBSERVED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    DELEGATION_RECORDED = "DELEGATION_RECORDED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_VERIFIED = "APPROVAL_VERIFIED"
    AUTHORITY_SUSPENDED = "AUTHORITY_SUSPENDED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    AUTHORITY_EXPIRED = "AUTHORITY_EXPIRED"
    AUTHORITY_DISPUTED = "AUTHORITY_DISPUTED"
    AUTHORITY_RETIRED = "AUTHORITY_RETIRED"
    AUTHORIZATION_PATTERN_VERIFIED = "AUTHORIZATION_PATTERN_VERIFIED"
    ESCALATION_PATTERN_VERIFIED = "ESCALATION_PATTERN_VERIFIED"
    CURRENT_AUTHORITY_CLAIM = "CURRENT_AUTHORITY_CLAIM"


CURRENT_CLAIM_TYPES = frozenset({RolePermissionEventType.CURRENT_AUTHORITY_CLAIM})
LESSON_TYPES = frozenset(
    {
        RolePermissionEventType.AUTHORIZATION_PATTERN_VERIFIED,
        RolePermissionEventType.ESCALATION_PATTERN_VERIFIED,
    }
)
SOURCE_BACKED_TYPES = frozenset(
    set(RolePermissionEventType)
    - {RolePermissionEventType.ROLE_OBSERVED}
    - CURRENT_CLAIM_TYPES
)
AUTHORIZING_BASES = frozenset(
    {
        AuthorityBasis.DIRECT_PERMISSION,
        AuthorityBasis.DELEGATION,
        AuthorityBasis.APPROVAL,
        AuthorityBasis.POLICY,
    }
)


@dataclass(frozen=True)
class RolePermissionEvent:
    event_id: str
    authority_id: str
    subject_id: str
    event_type: RolePermissionEventType
    authority_status: AuthorityStatus
    authority_basis: AuthorityBasis
    action: str
    resource: str
    scope_ref: str
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    repeat_count: int
    evidence_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    observer_refs: tuple[str, ...]
    role_refs: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ROLE_PERMISSION_EVENT_VERSION

    def __post_init__(self) -> None:
        required = (
            self.event_id,
            self.authority_id,
            self.subject_id,
            self.action,
            self.resource,
            self.scope_ref,
            self.statement,
            self.occurred_at,
        )
        if not all(required):
            raise ValueError("role permission event fields must not be empty")
        if self.schema_version != ROLE_PERMISSION_EVENT_VERSION:
            raise ValueError(f"unsupported role permission event: {self.schema_version}")
        if not 0.0 <= self.confidence <= 1.0 or self.repeat_count < 1:
            raise ValueError("invalid authority confidence or repeat_count")
        for name, values in (
            ("evidence_refs", self.evidence_refs),
            ("provenance_refs", self.provenance_refs),
            ("context_refs", self.context_refs),
            ("observer_refs", self.observer_refs),
            ("role_refs", self.role_refs),
            ("approval_refs", self.approval_refs),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")

        candidate = (
            self.identity_candidate_statement,
            self.identity_scope,
            self.identity_repeat_key,
        )
        if any(value is not None for value in candidate) and not all(candidate):
            raise ValueError("identity candidate fields must be set together")
        if all(candidate):
            self._validate_candidate()

        if self.event_type in SOURCE_BACKED_TYPES:
            if self.knowledge_class is not KnowledgeClass.FACT:
                raise ValueError("source-backed authority events require FACT")
            if not self.evidence_refs or not self.provenance_refs:
                raise ValueError("source-backed authority events require evidence and provenance")
        self._validate_contract()

    def _validate_candidate(self) -> None:
        if self.event_type not in LESSON_TYPES:
            raise ValueError("event cannot propose an authority lesson")
        if self.identity_scope != ROLES_PERMISSIONS_TRACK:
            raise ValueError("candidate scope must be roles.permissions")
        if self.knowledge_class is not KnowledgeClass.FACT:
            raise ValueError("authority candidate requires FACT")
        if self.repeat_count < 2:
            raise ValueError("authority candidate requires repeated evidence")
        if len(self.evidence_refs) < 2 or len(self.provenance_refs) < 2:
            raise ValueError("authority candidate requires two evidence and provenance refs")
        if len(self.context_refs) < 2 or len(self.observer_refs) < 2:
            raise ValueError("authority candidate requires cross-context independent evidence")

    def _validate_contract(self) -> None:
        expected = {
            RolePermissionEventType.ROLE_OBSERVED: AuthorityStatus.OBSERVED,
            RolePermissionEventType.ROLE_ASSIGNED: AuthorityStatus.ACTIVE,
            RolePermissionEventType.PERMISSION_GRANTED: AuthorityStatus.ACTIVE,
            RolePermissionEventType.PERMISSION_DENIED: AuthorityStatus.DENIED,
            RolePermissionEventType.DELEGATION_RECORDED: AuthorityStatus.ACTIVE,
            RolePermissionEventType.APPROVAL_REQUIRED: AuthorityStatus.PENDING_APPROVAL,
            RolePermissionEventType.APPROVAL_VERIFIED: AuthorityStatus.ACTIVE,
            RolePermissionEventType.AUTHORITY_SUSPENDED: AuthorityStatus.SUSPENDED,
            RolePermissionEventType.PERMISSION_REVOKED: AuthorityStatus.REVOKED,
            RolePermissionEventType.AUTHORITY_EXPIRED: AuthorityStatus.EXPIRED,
            RolePermissionEventType.AUTHORITY_DISPUTED: AuthorityStatus.DISPUTED,
            RolePermissionEventType.AUTHORITY_RETIRED: AuthorityStatus.RETIRED,
            RolePermissionEventType.AUTHORIZATION_PATTERN_VERIFIED: AuthorityStatus.ACTIVE,
            RolePermissionEventType.ESCALATION_PATTERN_VERIFIED: AuthorityStatus.PENDING_APPROVAL,
        }.get(self.event_type)
        if expected is not None and self.authority_status is not expected:
            raise ValueError(f"{self.event_type.value} requires {expected.value}")
        if self.event_type is RolePermissionEventType.ROLE_ASSIGNED:
            if self.authority_basis is not AuthorityBasis.ROLE_ASSIGNMENT:
                raise ValueError("role assignment requires ROLE_ASSIGNMENT basis")
        if self.event_type is RolePermissionEventType.DELEGATION_RECORDED:
            if self.authority_basis is not AuthorityBasis.DELEGATION:
                raise ValueError("delegation event requires DELEGATION basis")
        if self.event_type is RolePermissionEventType.APPROVAL_VERIFIED:
            if self.authority_basis is not AuthorityBasis.APPROVAL or not self.approval_refs:
                raise ValueError("approval verification requires APPROVAL basis and approval refs")

    @property
    def event_digest(self) -> str:
        return digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "authority_id": self.authority_id,
            "subject_id": self.subject_id,
            "event_type": self.event_type.value,
            "authority_status": self.authority_status.value,
            "authority_basis": self.authority_basis.value,
            "action": self.action,
            "resource": self.resource,
            "scope_ref": self.scope_ref,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "repeat_count": self.repeat_count,
            "evidence_refs": list(self.evidence_refs),
            "provenance_refs": list(self.provenance_refs),
            "context_refs": list(self.context_refs),
            "observer_refs": list(self.observer_refs),
            "role_refs": list(self.role_refs),
            "approval_refs": list(self.approval_refs),
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


def digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
