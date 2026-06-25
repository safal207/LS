"""Versioned contracts for the LS Authorization Decision Gate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .continuity_coordinator import ContinuityDecision
from .roles_permissions_contract import AuthorityBasis

AUTHORIZATION_REQUEST_VERSION = "trusted_runtime.authorization_request.v0.1"
AUTHORIZATION_RESULT_VERSION = "trusted_runtime.authorization_result.v0.1"
AUTHORIZATION_GATE_POLICY_VERSION = "authorization_decision_gate.v0.1"


class AuthorizationDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class CapabilityState(str, Enum):
    AVAILABLE = "AVAILABLE"
    RECOVERED = "RECOVERED"
    CONSTRAINED = "CONSTRAINED"
    UNAVAILABLE = "UNAVAILABLE"
    DISPUTED = "DISPUTED"
    EXPIRED = "EXPIRED"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class AuthorityState(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    DENIED = "DENIED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    DISPUTED = "DISPUTED"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class PolicyEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    UNKNOWN = "UNKNOWN"


class ApprovalState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    DENIED = "DENIED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class ContextState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class AuthorizationReason(str, Enum):
    POLICY_DENIED = "POLICY_DENIED"
    AUTHORITY_DENIED = "AUTHORITY_DENIED"
    AUTHORITY_REVOKED = "AUTHORITY_REVOKED"
    AUTHORITY_EXPIRED = "AUTHORITY_EXPIRED"
    AUTHORITY_RETIRED = "AUTHORITY_RETIRED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    APPROVAL_REVOKED = "APPROVAL_REVOKED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    CAPABILITY_CONSTRAINED = "CAPABILITY_CONSTRAINED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    CAPABILITY_EVIDENCE_BLOCKED = "CAPABILITY_EVIDENCE_BLOCKED"
    AUTHORITY_EVIDENCE_BLOCKED = "AUTHORITY_EVIDENCE_BLOCKED"
    SUBJECT_MISMATCH = "SUBJECT_MISMATCH"
    CAPABILITY_SUBJECT_BINDING_MISSING = "CAPABILITY_SUBJECT_BINDING_MISSING"
    CAPABILITY_UNVERIFIED = "CAPABILITY_UNVERIFIED"
    CAPABILITY_DISPUTED = "CAPABILITY_DISPUTED"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    AUTHORITY_UNVERIFIED = "AUTHORITY_UNVERIFIED"
    AUTHORITY_PENDING_APPROVAL = "AUTHORITY_PENDING_APPROVAL"
    AUTHORITY_SUSPENDED = "AUTHORITY_SUSPENDED"
    AUTHORITY_DISPUTED = "AUTHORITY_DISPUTED"
    AUTHORITY_UNKNOWN = "AUTHORITY_UNKNOWN"
    AUTHORITY_BASIS_INSUFFICIENT = "AUTHORITY_BASIS_INSUFFICIENT"
    AUTHORITY_SCOPE_MISMATCH = "AUTHORITY_SCOPE_MISMATCH"
    AUTHORITY_PROVENANCE_MISSING = "AUTHORITY_PROVENANCE_MISSING"
    POLICY_UNKNOWN = "POLICY_UNKNOWN"
    POLICY_SCOPE_MISMATCH = "POLICY_SCOPE_MISMATCH"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVAL_UNKNOWN = "APPROVAL_UNKNOWN"
    APPROVAL_SCOPE_MISMATCH = "APPROVAL_SCOPE_MISMATCH"
    APPROVAL_REFERENCE_MISMATCH = "APPROVAL_REFERENCE_MISMATCH"
    CONTEXT_STALE = "CONTEXT_STALE"
    CONTEXT_UNKNOWN = "CONTEXT_UNKNOWN"
    CONTEXT_SCOPE_MISMATCH = "CONTEXT_SCOPE_MISMATCH"
    CONTEXT_TOO_OLD = "CONTEXT_TOO_OLD"
    CAPABILITY_VERIFIED = "CAPABILITY_VERIFIED"
    AUTHORITY_VERIFIED = "AUTHORITY_VERIFIED"
    POLICY_ALLOWED = "POLICY_ALLOWED"
    APPROVAL_VERIFIED = "APPROVAL_VERIFIED"
    APPROVAL_NOT_REQUIRED = "APPROVAL_NOT_REQUIRED"
    CONTEXT_FRESH = "CONTEXT_FRESH"


@dataclass(frozen=True)
class CapabilityEvidence:
    result_id: str
    assessment_id: str
    assessment_decision: ContinuityDecision
    subject_id: str
    capability_id: str
    state: CapabilityState
    evidence_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    result_digest: str

    def __post_init__(self) -> None:
        _require_strings(
            self.result_id,
            self.assessment_id,
            self.subject_id,
            self.capability_id,
            self.result_digest,
        )
        _validate_refs("capability evidence_refs", self.evidence_refs)
        _validate_refs("capability context_refs", self.context_refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "assessment_id": self.assessment_id,
            "assessment_decision": self.assessment_decision.value,
            "subject_id": self.subject_id,
            "capability_id": self.capability_id,
            "state": self.state.value,
            "evidence_refs": list(self.evidence_refs),
            "context_refs": list(self.context_refs),
            "result_digest": self.result_digest,
        }


@dataclass(frozen=True)
class AuthorityEvidence:
    result_id: str
    assessment_id: str
    assessment_decision: ContinuityDecision
    subject_id: str
    authority_id: str
    state: AuthorityState
    basis: AuthorityBasis
    action: str
    resource: str
    scope_ref: str
    evidence_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    approval_refs: tuple[str, ...]
    result_digest: str

    def __post_init__(self) -> None:
        _require_strings(
            self.result_id,
            self.assessment_id,
            self.subject_id,
            self.authority_id,
            self.result_digest,
        )
        for name, refs in (
            ("authority evidence_refs", self.evidence_refs),
            ("authority provenance_refs", self.provenance_refs),
            ("authority approval_refs", self.approval_refs),
        ):
            _validate_refs(name, refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "assessment_id": self.assessment_id,
            "assessment_decision": self.assessment_decision.value,
            "subject_id": self.subject_id,
            "authority_id": self.authority_id,
            "state": self.state.value,
            "basis": self.basis.value,
            "action": self.action,
            "resource": self.resource,
            "scope_ref": self.scope_ref,
            "evidence_refs": list(self.evidence_refs),
            "provenance_refs": list(self.provenance_refs),
            "approval_refs": list(self.approval_refs),
            "result_digest": self.result_digest,
        }


@dataclass(frozen=True)
class PolicyEvidence:
    policy_id: str
    policy_version: str
    effect: PolicyEffect
    action: str
    resource: str
    scope_ref: str
    evidence_refs: tuple[str, ...]
    policy_digest: str

    def __post_init__(self) -> None:
        _require_strings(self.policy_id, self.policy_version, self.policy_digest)
        _validate_refs("policy evidence_refs", self.evidence_refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "effect": self.effect.value,
            "action": self.action,
            "resource": self.resource,
            "scope_ref": self.scope_ref,
            "evidence_refs": list(self.evidence_refs),
            "policy_digest": self.policy_digest,
        }


@dataclass(frozen=True)
class ApprovalEvidence:
    approval_id: str
    subject_id: str
    state: ApprovalState
    action: str
    resource: str
    scope_ref: str
    approver_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    approval_digest: str

    def __post_init__(self) -> None:
        _require_strings(self.approval_id, self.subject_id, self.approval_digest)
        _validate_refs("approval approver_refs", self.approver_refs)
        _validate_refs("approval evidence_refs", self.evidence_refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "subject_id": self.subject_id,
            "state": self.state.value,
            "action": self.action,
            "resource": self.resource,
            "scope_ref": self.scope_ref,
            "approver_refs": list(self.approver_refs),
            "evidence_refs": list(self.evidence_refs),
            "approval_digest": self.approval_digest,
        }


@dataclass(frozen=True)
class ExecutionContextEvidence:
    context_id: str
    subject_id: str
    state: ContextState
    action: str
    resource: str
    scope_ref: str
    age_seconds: int
    max_age_seconds: int
    evidence_refs: tuple[str, ...]
    context_digest: str

    def __post_init__(self) -> None:
        _require_strings(self.context_id, self.subject_id, self.context_digest)
        if self.age_seconds < 0 or self.max_age_seconds < 0:
            raise ValueError("context ages must be non-negative")
        _validate_refs("context evidence_refs", self.evidence_refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "subject_id": self.subject_id,
            "state": self.state.value,
            "action": self.action,
            "resource": self.resource,
            "scope_ref": self.scope_ref,
            "age_seconds": self.age_seconds,
            "max_age_seconds": self.max_age_seconds,
            "evidence_refs": list(self.evidence_refs),
            "context_digest": self.context_digest,
        }


@dataclass(frozen=True)
class AuthorizationRequest:
    request_id: str
    subject_id: str
    intent_ref: str
    action: str
    resource: str
    scope_ref: str
    required_capability_id: str
    capability_subject_binding_ref: str
    capability: CapabilityEvidence
    authority: AuthorityEvidence
    policy: PolicyEvidence
    approval: ApprovalEvidence
    context: ExecutionContextEvidence
    requested_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = AUTHORIZATION_REQUEST_VERSION

    def __post_init__(self) -> None:
        _require_strings(
            self.request_id,
            self.subject_id,
            self.intent_ref,
            self.action,
            self.resource,
            self.scope_ref,
            self.required_capability_id,
            self.requested_at,
        )
        if not isinstance(self.capability_subject_binding_ref, str):
            raise ValueError("capability_subject_binding_ref must be a string")
        if self.schema_version != AUTHORIZATION_REQUEST_VERSION:
            raise ValueError(f"unsupported authorization request: {self.schema_version}")

    @property
    def request_digest(self) -> str:
        return digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "subject_id": self.subject_id,
            "intent_ref": self.intent_ref,
            "action": self.action,
            "resource": self.resource,
            "scope_ref": self.scope_ref,
            "required_capability_id": self.required_capability_id,
            "capability_subject_binding_ref": self.capability_subject_binding_ref,
            "capability": self.capability.to_dict(),
            "authority": self.authority.to_dict(),
            "policy": self.policy.to_dict(),
            "approval": self.approval.to_dict(),
            "context": self.context.to_dict(),
            "requested_at": self.requested_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AuthorizationResult:
    decision_id: str
    request_id: str
    request_digest: str
    decision: AuthorizationDecision
    reason_codes: tuple[AuthorizationReason, ...]
    action_authorized: bool
    evaluated_at: str
    evaluated_by: str = "runtime:authorization-decision-gate"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = AUTHORIZATION_GATE_POLICY_VERSION
    schema_version: str = AUTHORIZATION_RESULT_VERSION

    def __post_init__(self) -> None:
        _require_strings(
            self.decision_id,
            self.request_id,
            self.request_digest,
            self.evaluated_at,
            self.evaluated_by,
        )
        if self.schema_version != AUTHORIZATION_RESULT_VERSION:
            raise ValueError(f"unsupported authorization result: {self.schema_version}")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("authorization reason codes must be unique")
        if self.action_authorized is not (self.decision is AuthorizationDecision.ALLOW):
            raise ValueError("action_authorized must match ALLOW decision")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "decision": self.decision.value,
            "reason_codes": [reason.value for reason in self.reason_codes],
            "action_authorized": self.action_authorized,
            "capability_registry_mutation_allowed": False,
            "role_registry_mutation_allowed": False,
            "permission_registry_mutation_allowed": False,
            "approval_mutation_allowed": False,
            "policy_mutation_allowed": False,
            "context_mutation_allowed": False,
            "work_scheduling_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "evaluated_at": self.evaluated_at,
            "evaluated_by": self.evaluated_by,
            "metadata": dict(self.metadata),
        }


def digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_strings(*values: str) -> None:
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError("required authorization fields must not be empty")


def _validate_refs(name: str, refs: tuple[str, ...]) -> None:
    if len(refs) != len(set(refs)):
        raise ValueError(f"{name} must be unique")
    if any(not isinstance(ref, str) or not ref for ref in refs):
        raise ValueError(f"{name} must contain non-empty strings")


__all__ = [
    "AUTHORIZATION_GATE_POLICY_VERSION",
    "ApprovalEvidence",
    "ApprovalState",
    "AuthorityEvidence",
    "AuthorityState",
    "AuthorizationDecision",
    "AuthorizationReason",
    "AuthorizationRequest",
    "AuthorizationResult",
    "CapabilityEvidence",
    "CapabilityState",
    "ContextState",
    "ExecutionContextEvidence",
    "PolicyEffect",
    "PolicyEvidence",
]
