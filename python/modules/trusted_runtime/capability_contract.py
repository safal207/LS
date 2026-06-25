from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from .continuity_coordinator import KnowledgeClass

CAPABILITY_EVENT_VERSION = "trusted_runtime.capability_constraint_event.v0.1"
CAPABILITIES_TRACK = "capabilities.constraints"


class CapabilityStatus(str, Enum):
    OBSERVED = "OBSERVED"
    AVAILABLE = "AVAILABLE"
    CONSTRAINED = "CONSTRAINED"
    DISPUTED = "DISPUTED"
    UNAVAILABLE = "UNAVAILABLE"
    RECOVERED = "RECOVERED"
    EXPIRED = "EXPIRED"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class ConstraintKind(str, Enum):
    NONE = "NONE"
    CONTEXTUAL = "CONTEXTUAL"
    TEMPORARY = "TEMPORARY"
    RESOURCE = "RESOURCE"
    POLICY = "POLICY"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    UNKNOWN = "UNKNOWN"


class CapabilityEventType(str, Enum):
    ABILITY_OBSERVED = "ABILITY_OBSERVED"
    CAPABILITY_VERIFIED = "CAPABILITY_VERIFIED"
    CONSTRAINT_RECORDED = "CONSTRAINT_RECORDED"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    CAPABILITY_DISPUTED = "CAPABILITY_DISPUTED"
    CAPABILITY_RECOVERED = "CAPABILITY_RECOVERED"
    CONSTRAINT_EXPIRED = "CONSTRAINT_EXPIRED"
    CAPABILITY_RETIRED = "CAPABILITY_RETIRED"
    CAPABILITY_PATTERN_VERIFIED = "CAPABILITY_PATTERN_VERIFIED"
    RECOVERY_PATTERN_VERIFIED = "RECOVERY_PATTERN_VERIFIED"
    CURRENT_CAPABILITY_CLAIM = "CURRENT_CAPABILITY_CLAIM"
    CURRENT_LIMITATION_CLAIM = "CURRENT_LIMITATION_CLAIM"


CURRENT_CLAIM_TYPES = frozenset(
    {
        CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
        CapabilityEventType.CURRENT_LIMITATION_CLAIM,
    }
)
LESSON_TYPES = frozenset(
    {
        CapabilityEventType.CAPABILITY_PATTERN_VERIFIED,
        CapabilityEventType.RECOVERY_PATTERN_VERIFIED,
    }
)
SOURCE_BACKED_TYPES = frozenset(
    set(CapabilityEventType)
    - {CapabilityEventType.ABILITY_OBSERVED}
    - CURRENT_CLAIM_TYPES
)
ACTIVE_CONSTRAINTS = frozenset(
    {
        ConstraintKind.CONTEXTUAL,
        ConstraintKind.TEMPORARY,
        ConstraintKind.RESOURCE,
        ConstraintKind.POLICY,
        ConstraintKind.ENVIRONMENTAL,
    }
)


@dataclass(frozen=True)
class CapabilityConstraintEvent:
    event_id: str
    capability_id: str
    event_type: CapabilityEventType
    capability_status: CapabilityStatus
    constraint_kind: ConstraintKind
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    repeat_count: int
    evidence_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    observer_refs: tuple[str, ...]
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = CAPABILITY_EVENT_VERSION

    def __post_init__(self) -> None:
        if not all((self.event_id, self.capability_id, self.statement, self.occurred_at)):
            raise ValueError("capability event fields must not be empty")
        if self.schema_version != CAPABILITY_EVENT_VERSION:
            raise ValueError(f"unsupported capability event: {self.schema_version}")
        if not 0.0 <= self.confidence <= 1.0 or self.repeat_count < 1:
            raise ValueError("invalid capability confidence or repeat_count")
        for name, values in (
            ("evidence_refs", self.evidence_refs),
            ("context_refs", self.context_refs),
            ("observer_refs", self.observer_refs),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        candidate = (
            self.identity_candidate_statement,
            self.identity_scope,
            self.identity_repeat_key,
        )
        if any(value is not None for value in candidate) and not all(candidate):
            raise ValueError("candidate fields must be set together")
        if all(candidate):
            self._validate_candidate()
        if self.event_type in SOURCE_BACKED_TYPES:
            if self.knowledge_class is not KnowledgeClass.FACT:
                raise ValueError("source-backed capability events require FACT")
            if not self.evidence_refs:
                raise ValueError("source-backed capability events require evidence")
        self._validate_contract()

    def _validate_candidate(self) -> None:
        if self.event_type not in LESSON_TYPES:
            raise ValueError("event cannot propose a capability lesson")
        if self.identity_scope != CAPABILITIES_TRACK:
            raise ValueError("candidate scope must be capabilities.constraints")
        if self.knowledge_class is not KnowledgeClass.FACT:
            raise ValueError("capability candidate requires FACT")
        if self.repeat_count < 2:
            raise ValueError("capability candidate requires repeated evidence")
        if len(self.evidence_refs) < 2:
            raise ValueError("capability candidate requires two evidence refs")
        if len(self.context_refs) < 2:
            raise ValueError("capability candidate requires cross-context evidence")
        if len(self.observer_refs) < 2:
            raise ValueError("capability candidate requires independent observers")
        expected = (
            CapabilityStatus.AVAILABLE
            if self.event_type is CapabilityEventType.CAPABILITY_PATTERN_VERIFIED
            else CapabilityStatus.RECOVERED
        )
        if self.capability_status is not expected:
            raise ValueError(f"candidate requires {expected.value} status")
        if self.constraint_kind is not ConstraintKind.NONE:
            raise ValueError("candidate requires no active constraint")

    def _validate_contract(self) -> None:
        expected = {
            CapabilityEventType.ABILITY_OBSERVED: CapabilityStatus.OBSERVED,
            CapabilityEventType.CAPABILITY_VERIFIED: CapabilityStatus.AVAILABLE,
            CapabilityEventType.CONSTRAINT_RECORDED: CapabilityStatus.CONSTRAINED,
            CapabilityEventType.RESOURCE_UNAVAILABLE: CapabilityStatus.UNAVAILABLE,
            CapabilityEventType.CAPABILITY_DISPUTED: CapabilityStatus.DISPUTED,
            CapabilityEventType.CAPABILITY_RECOVERED: CapabilityStatus.RECOVERED,
            CapabilityEventType.CONSTRAINT_EXPIRED: CapabilityStatus.EXPIRED,
            CapabilityEventType.CAPABILITY_RETIRED: CapabilityStatus.RETIRED,
            CapabilityEventType.CAPABILITY_PATTERN_VERIFIED: CapabilityStatus.AVAILABLE,
            CapabilityEventType.RECOVERY_PATTERN_VERIFIED: CapabilityStatus.RECOVERED,
        }.get(self.event_type)
        if expected is not None and self.capability_status is not expected:
            raise ValueError(f"{self.event_type.value} requires {expected.value}")
        if self.event_type is CapabilityEventType.CONSTRAINT_RECORDED:
            if self.constraint_kind not in ACTIVE_CONSTRAINTS:
                raise ValueError("constraint event requires a bounded kind")
        if self.event_type is CapabilityEventType.RESOURCE_UNAVAILABLE:
            if self.constraint_kind is not ConstraintKind.RESOURCE:
                raise ValueError("resource event requires RESOURCE constraint")
        if self.event_type is CapabilityEventType.CURRENT_LIMITATION_CLAIM:
            if self.constraint_kind is ConstraintKind.NONE:
                raise ValueError("limitation claim requires a constraint kind")

    @property
    def event_digest(self) -> str:
        return digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "capability_id": self.capability_id,
            "event_type": self.event_type.value,
            "capability_status": self.capability_status.value,
            "constraint_kind": self.constraint_kind.value,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "repeat_count": self.repeat_count,
            "evidence_refs": list(self.evidence_refs),
            "context_refs": list(self.context_refs),
            "observer_refs": list(self.observer_refs),
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


def digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
