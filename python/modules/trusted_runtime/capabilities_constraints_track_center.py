"""Governed Capabilities/Constraints Track Center for LS.

The center distinguishes observed ability, verified capability, contextual
constraint, resource unavailability, recovery, expiry, retirement, dispute,
and current-incapability claims. It may emit only a bounded LessonCandidate
from repeated cross-context verified capability or recovery. It never mutates
a capability registry, denies access, assigns permanent incapacity, schedules
training, changes priorities, updates stable identity, or authorizes execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from .continuity_coordinator import (
    ContinuityAssessment,
    EntityStatus,
    KnowledgeClass,
    TrackObservation,
    assess_track_observation,
)


CAPABILITY_EVENT_VERSION = "trusted_runtime.capability_constraint_event.v0.1"
CAPABILITY_RESULT_VERSION = "trusted_runtime.capability_constraint_result.v0.1"
CAPABILITY_POLICY_VERSION = "capabilities_constraints_track_center.v0.1"
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


class CapabilityScope(str, Enum):
    LOCAL = "LOCAL"
    PROJECT = "PROJECT"
    CROSS_CONTEXT = "CROSS_CONTEXT"


class CapabilityEventType(str, Enum):
    ABILITY_OBSERVED = "ABILITY_OBSERVED"
    CAPABILITY_VERIFIED = "CAPABILITY_VERIFIED"
    CONSTRAINT_RECORDED = "CONSTRAINT_RECORDED"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    CAPABILITY_RECOVERED = "CAPABILITY_RECOVERED"
    CONSTRAINT_EXPIRED = "CONSTRAINT_EXPIRED"
    CAPABILITY_RETIRED = "CAPABILITY_RETIRED"
    CAPABILITY_DISPUTED = "CAPABILITY_DISPUTED"
    REPEATED_CAPABILITY_VERIFIED = "REPEATED_CAPABILITY_VERIFIED"
    REPEATED_RECOVERY_VERIFIED = "REPEATED_RECOVERY_VERIFIED"
    CURRENT_INCAPABILITY_CLAIM = "CURRENT_INCAPABILITY_CLAIM"


CURRENT_INCAPABILITY_EVENT_TYPES = frozenset(
    {CapabilityEventType.CURRENT_INCAPABILITY_CLAIM}
)
LESSON_CANDIDATE_EVENT_TYPES = frozenset(
    {
        CapabilityEventType.REPEATED_CAPABILITY_VERIFIED,
        CapabilityEventType.REPEATED_RECOVERY_VERIFIED,
    }
)
SOURCE_BACKED_EVENT_TYPES = frozenset(
    {
        CapabilityEventType.CAPABILITY_VERIFIED,
        CapabilityEventType.CONSTRAINT_RECORDED,
        CapabilityEventType.RESOURCE_UNAVAILABLE,
        CapabilityEventType.CAPABILITY_RECOVERED,
        CapabilityEventType.CONSTRAINT_EXPIRED,
        CapabilityEventType.CAPABILITY_RETIRED,
        CapabilityEventType.CAPABILITY_DISPUTED,
        CapabilityEventType.REPEATED_CAPABILITY_VERIFIED,
        CapabilityEventType.REPEATED_RECOVERY_VERIFIED,
        CapabilityEventType.CURRENT_INCAPABILITY_CLAIM,
    }
)
CURRENT_INCAPABILITY_BLOCKED_STATUSES = frozenset(
    {
        CapabilityStatus.AVAILABLE,
        CapabilityStatus.RECOVERED,
        CapabilityStatus.EXPIRED,
        CapabilityStatus.RETIRED,
    }
)
CURRENT_INCAPABILITY_HELD_STATUSES = frozenset(
    {
        CapabilityStatus.OBSERVED,
        CapabilityStatus.DISPUTED,
        CapabilityStatus.UNKNOWN,
    }
)


@dataclass(frozen=True)
class CapabilityConstraintEvent:
    event_id: str
    capability_id: str
    event_type: CapabilityEventType
    capability_status: CapabilityStatus
    capability_scope: CapabilityScope
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    repeat_count: int
    evidence_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    capability_refs: tuple[str, ...]
    resource_refs: tuple[str, ...] = ()
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = CAPABILITY_EVENT_VERSION

    def __post_init__(self) -> None:
        if not all(
            (
                self.event_id,
                self.capability_id,
                self.statement,
                self.occurred_at,
            )
        ):
            raise ValueError("capability constraint event fields must not be empty")
        if self.schema_version != CAPABILITY_EVENT_VERSION:
            raise ValueError(
                f"unsupported capability constraint event: {self.schema_version}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("capability confidence must be between 0 and 1")
        if self.repeat_count < 1:
            raise ValueError("capability repeat_count must be at least 1")
        _require_unique("evidence_refs", self.evidence_refs)
        _require_unique("context_refs", self.context_refs)
        _require_unique("capability_refs", self.capability_refs)
        _require_unique("resource_refs", self.resource_refs)

        identity_fields = (
            self.identity_candidate_statement,
            self.identity_scope,
            self.identity_repeat_key,
        )
        has_candidate = any(value is not None for value in identity_fields)
        if has_candidate and not all(identity_fields):
            raise ValueError(
                "identity candidate statement, scope, and repeat_key "
                "must be set together"
            )
        if has_candidate:
            self._validate_lesson_candidate()

        if self.event_type in SOURCE_BACKED_EVENT_TYPES:
            if self.knowledge_class is not KnowledgeClass.FACT:
                raise ValueError("source-backed capability events require FACT knowledge")
            if not self.evidence_refs:
                raise ValueError("source-backed capability events require evidence")

        self._validate_event_contract()

    def _validate_lesson_candidate(self) -> None:
        if self.event_type not in LESSON_CANDIDATE_EVENT_TYPES:
            raise ValueError(
                "this capability event type cannot propose an identity lesson"
            )
        if self.identity_scope != CAPABILITIES_TRACK:
            raise ValueError(
                "capability lesson candidates must use capabilities.constraints scope"
            )
        if self.knowledge_class is not KnowledgeClass.FACT:
            raise ValueError("capability lesson candidate requires FACT knowledge")
        if self.capability_scope is not CapabilityScope.CROSS_CONTEXT:
            raise ValueError(
                "capability lesson candidate requires CROSS_CONTEXT scope"
            )
        if self.repeat_count < 2:
            raise ValueError("capability lesson candidate requires repeated evidence")
        if len(self.evidence_refs) < 2:
            raise ValueError(
                "capability lesson candidate requires two evidence refs"
            )
        if len(self.context_refs) < 2:
            raise ValueError(
                "capability lesson candidate requires cross-context evidence"
            )
        if len(self.capability_refs) < 2:
            raise ValueError(
                "capability lesson candidate requires distinct capability observations"
            )

        if self.event_type is CapabilityEventType.REPEATED_CAPABILITY_VERIFIED:
            if self.capability_status is not CapabilityStatus.AVAILABLE:
                raise ValueError(
                    "repeated capability candidate requires AVAILABLE status"
                )
        elif self.capability_status is not CapabilityStatus.RECOVERED:
            raise ValueError("repeated recovery candidate requires RECOVERED status")

    def _validate_event_contract(self) -> None:
        status_by_event = {
            CapabilityEventType.ABILITY_OBSERVED: CapabilityStatus.OBSERVED,
            CapabilityEventType.CAPABILITY_VERIFIED: CapabilityStatus.AVAILABLE,
            CapabilityEventType.CONSTRAINT_RECORDED: CapabilityStatus.CONSTRAINED,
            CapabilityEventType.RESOURCE_UNAVAILABLE: CapabilityStatus.UNAVAILABLE,
            CapabilityEventType.CAPABILITY_RECOVERED: CapabilityStatus.RECOVERED,
            CapabilityEventType.CONSTRAINT_EXPIRED: CapabilityStatus.EXPIRED,
            CapabilityEventType.CAPABILITY_RETIRED: CapabilityStatus.RETIRED,
            CapabilityEventType.CAPABILITY_DISPUTED: CapabilityStatus.DISPUTED,
            CapabilityEventType.REPEATED_CAPABILITY_VERIFIED: (
                CapabilityStatus.AVAILABLE
            ),
            CapabilityEventType.REPEATED_RECOVERY_VERIFIED: (
                CapabilityStatus.RECOVERED
            ),
        }
        required_status = status_by_event.get(self.event_type)
        if required_status is not None and self.capability_status is not required_status:
            raise ValueError(
                f"{self.event_type.value} requires {required_status.value} status"
            )

        if self.event_type is CapabilityEventType.RESOURCE_UNAVAILABLE:
            if not self.resource_refs:
                raise ValueError("resource unavailability requires resource refs")

        if self.event_type is CapabilityEventType.CURRENT_INCAPABILITY_CLAIM:
            allowed = (
                CURRENT_INCAPABILITY_BLOCKED_STATUSES
                | CURRENT_INCAPABILITY_HELD_STATUSES
                | {
                    CapabilityStatus.CONSTRAINED,
                    CapabilityStatus.UNAVAILABLE,
                }
            )
            if self.capability_status not in allowed:
                raise ValueError(
                    "unsupported status for current incapability claim"
                )
            if self.capability_scope is CapabilityScope.CROSS_CONTEXT:
                if len(self.context_refs) < 2:
                    raise ValueError(
                        "cross-context incapability claim requires two contexts"
                    )
            elif not self.context_refs:
                raise ValueError(
                    "current incapability claim requires explicit context"
                )

    @property
    def event_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "capability_id": self.capability_id,
            "event_type": self.event_type.value,
            "capability_status": self.capability_status.value,
            "capability_scope": self.capability_scope.value,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "repeat_count": self.repeat_count,
            "evidence_refs": list(self.evidence_refs),
            "context_refs": list(self.context_refs),
            "capability_refs": list(self.capability_refs),
            "resource_refs": list(self.resource_refs),
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CapabilityConstraintResult:
    result_id: str
    event: CapabilityConstraintEvent
    observation: TrackObservation
    assessment: ContinuityAssessment
    processed_at: str
    processed_by: str = "runtime:capabilities-constraints-track-center"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = CAPABILITY_POLICY_VERSION
    schema_version: str = CAPABILITY_RESULT_VERSION

    def __post_init__(self) -> None:
        if not all((self.result_id, self.processed_at, self.processed_by)):
            raise ValueError("capability constraint result fields must not be empty")
        if self.schema_version != CAPABILITY_RESULT_VERSION:
            raise ValueError(
                f"unsupported capability constraint result: {self.schema_version}"
            )
        if self.event.capability_id != self.observation.subject_id:
            raise ValueError("capability event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("capability observation and assessment mismatch")
        if self.observation.track != CAPABILITIES_TRACK:
            raise ValueError("capability result requires canonical capability track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "capability_registry_mutation_allowed": False,
            "access_denial_allowed": False,
            "permanent_incapacity_assignment_allowed": False,
            "training_scheduling_allowed": False,
            "priority_mutation_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_capability_observation(
    event: CapabilityConstraintEvent,
) -> TrackObservation:
    candidate = event.event_type in LESSON_CANDIDATE_EVENT_TYPES
    current_incapability = event.event_type in CURRENT_INCAPABILITY_EVENT_TYPES
    observation_id = "capability-observation:sha256:" + _digest(
        {
            "event_id": event.event_id,
            "event_digest": event.event_digest,
            "track": CAPABILITIES_TRACK,
            "policy_version": CAPABILITY_POLICY_VERSION,
        }
    )
    return TrackObservation(
        observation_id=observation_id,
        track=CAPABILITIES_TRACK,
        subject_id=event.capability_id,
        entity_status=_entity_status(event),
        knowledge_class=event.knowledge_class,
        statement=event.statement,
        occurred_at=event.occurred_at,
        confidence=event.confidence,
        evidence_refs=event.evidence_refs,
        claims_current_presence=current_incapability,
        identity_candidate_statement=(
            event.identity_candidate_statement if candidate else None
        ),
        identity_scope=event.identity_scope if candidate else None,
        identity_repeat_key=event.identity_repeat_key if candidate else None,
        metadata={
            "capability_id": event.capability_id,
            "capability_event_id": event.event_id,
            "capability_event_digest": event.event_digest,
            "capability_event_type": event.event_type.value,
            "capability_status": event.capability_status.value,
            "capability_scope": event.capability_scope.value,
            "repeat_count": event.repeat_count,
            "context_refs": list(event.context_refs),
            "capability_refs": list(event.capability_refs),
            "resource_refs": list(event.resource_refs),
            "temporary_constraint_is_not_permanent_incapacity": True,
            "local_failure_is_not_global_inability": True,
            "track_center_policy_version": CAPABILITY_POLICY_VERSION,
            "capability_registry_mutation_allowed": False,
            "access_denial_allowed": False,
            "permanent_incapacity_assignment_allowed": False,
            "training_scheduling_allowed": False,
            "priority_mutation_allowed": False,
        },
    )


def process_capability_event(
    event: CapabilityConstraintEvent,
    *,
    processed_at: str,
    processed_by: str = "runtime:capabilities-constraints-track-center",
) -> CapabilityConstraintResult:
    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")
    observation = build_capability_observation(event)
    assessment = assess_track_observation(
        observation,
        assessed_at=processed_at,
        assessed_by="runtime:continuity-coordinator",
    )
    result_id = "capability-constraint-result:sha256:" + _digest(
        {
            "event_digest": event.event_digest,
            "observation_digest": observation.observation_digest,
            "assessment_id": assessment.assessment_id,
            "policy_version": CAPABILITY_POLICY_VERSION,
        }
    )
    return CapabilityConstraintResult(
        result_id=result_id,
        event=event,
        observation=observation,
        assessment=assessment,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "handoff": (
                "capability_event -> track_observation -> continuity_assessment"
            ),
            "temporary_constraint_is_not_permanent_incapacity": True,
            "local_failure_is_not_global_inability": True,
            "cross_context_repetition_required_for_candidate": True,
            "single_event_cannot_modify_stable_identity": True,
            "capability_update": "separate_governed_operation",
        },
    )


def _entity_status(event: CapabilityConstraintEvent) -> EntityStatus:
    status = event.capability_status
    if event.event_type is CapabilityEventType.CURRENT_INCAPABILITY_CLAIM:
        if status in CURRENT_INCAPABILITY_BLOCKED_STATUSES:
            return EntityStatus.CLOSED
        if status is CapabilityStatus.DISPUTED:
            return EntityStatus.PAUSED
        if status in {CapabilityStatus.OBSERVED, CapabilityStatus.UNKNOWN}:
            return EntityStatus.UNKNOWN
        return EntityStatus.ACTIVE

    if status in {
        CapabilityStatus.AVAILABLE,
        CapabilityStatus.CONSTRAINED,
        CapabilityStatus.UNAVAILABLE,
    }:
        return EntityStatus.ACTIVE
    if status is CapabilityStatus.DISPUTED:
        return EntityStatus.PAUSED
    if status in {
        CapabilityStatus.RECOVERED,
        CapabilityStatus.EXPIRED,
        CapabilityStatus.RETIRED,
    }:
        return EntityStatus.CLOSED
    return EntityStatus.UNKNOWN


def _require_unique(name: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
