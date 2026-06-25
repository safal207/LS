"""Governed Values Track Center for LS.

The center distinguishes durable value evidence from moods, preferences, and
single statements. It may emit only a bounded LessonCandidate after repeated,
cross-context, source-backed evidence. It never mutates the value registry,
priorities, stable identity, or authorizes execution.
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


VALUE_EVENT_VERSION = "trusted_runtime.value_event.v0.1"
VALUE_RESULT_VERSION = "trusted_runtime.value_track_result.v0.1"
VALUE_POLICY_VERSION = "values_track_center.v0.1"
VALUES_TRACK = "values.evidence"


class ValueStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    CONTESTED = "CONTESTED"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class ValueEventType(str, Enum):
    VALUE_SIGNAL_OBSERVED = "VALUE_SIGNAL_OBSERVED"
    VALUE_REAFFIRMED = "VALUE_REAFFIRMED"
    VALUE_PRACTICED = "VALUE_PRACTICED"
    VALUE_CONFLICT_RECORDED = "VALUE_CONFLICT_RECORDED"
    VALUE_RETIRED = "VALUE_RETIRED"
    TRANSIENT_PREFERENCE_OBSERVED = "TRANSIENT_PREFERENCE_OBSERVED"
    MOOD_SIGNAL_OBSERVED = "MOOD_SIGNAL_OBSERVED"
    CURRENT_VALUE_CLAIM = "CURRENT_VALUE_CLAIM"


CURRENT_VALUE_EVENT_TYPES = frozenset(
    {
        ValueEventType.VALUE_REAFFIRMED,
        ValueEventType.VALUE_PRACTICED,
        ValueEventType.CURRENT_VALUE_CLAIM,
    }
)

IDENTITY_CANDIDATE_EVENT_TYPES = frozenset(
    {
        ValueEventType.VALUE_REAFFIRMED,
        ValueEventType.VALUE_PRACTICED,
    }
)

SOURCE_BACKED_EVENT_TYPES = frozenset(
    {
        ValueEventType.VALUE_REAFFIRMED,
        ValueEventType.VALUE_PRACTICED,
        ValueEventType.VALUE_CONFLICT_RECORDED,
        ValueEventType.VALUE_RETIRED,
        ValueEventType.CURRENT_VALUE_CLAIM,
    }
)


@dataclass(frozen=True)
class ValueEvent:
    event_id: str
    value_key: str
    event_type: ValueEventType
    value_status: ValueStatus
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    repeat_count: int
    evidence_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = VALUE_EVENT_VERSION

    def __post_init__(self) -> None:
        required = (
            self.event_id,
            self.value_key,
            self.statement,
            self.occurred_at,
        )
        if not all(required):
            raise ValueError("value event fields must not be empty")
        if self.schema_version != VALUE_EVENT_VERSION:
            raise ValueError(f"unsupported value event: {self.schema_version}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("value confidence must be between 0 and 1")
        if self.repeat_count < 1:
            raise ValueError("value repeat_count must be at least 1")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("value evidence_refs must be unique")
        if len(self.context_refs) != len(set(self.context_refs)):
            raise ValueError("value context_refs must be unique")

        identity_fields = (
            self.identity_candidate_statement,
            self.identity_scope,
            self.identity_repeat_key,
        )
        has_identity_candidate = any(value is not None for value in identity_fields)
        if has_identity_candidate and not all(identity_fields):
            raise ValueError(
                "identity candidate statement, scope, and repeat_key "
                "must be set together"
            )
        if has_identity_candidate:
            self._validate_identity_candidate()

        if self.event_type in SOURCE_BACKED_EVENT_TYPES:
            if self.knowledge_class is not KnowledgeClass.FACT:
                raise ValueError("source-backed value events require FACT knowledge")
            if not self.evidence_refs:
                raise ValueError("source-backed value events require evidence")

        if self.event_type is ValueEventType.VALUE_RETIRED:
            if self.value_status is not ValueStatus.RETIRED:
                raise ValueError("VALUE_RETIRED requires RETIRED status")
        if self.event_type is ValueEventType.VALUE_CONFLICT_RECORDED:
            if self.value_status is not ValueStatus.CONTESTED:
                raise ValueError("VALUE_CONFLICT_RECORDED requires CONTESTED status")

    def _validate_identity_candidate(self) -> None:
        if self.event_type not in IDENTITY_CANDIDATE_EVENT_TYPES:
            raise ValueError("this value event type cannot propose an identity lesson")
        if self.value_status is not ValueStatus.ACTIVE:
            raise ValueError("identity value candidate requires ACTIVE status")
        if self.knowledge_class is not KnowledgeClass.FACT:
            raise ValueError("identity value candidate requires FACT knowledge")
        if self.repeat_count < 2:
            raise ValueError("identity value candidate requires repeated evidence")
        if len(self.evidence_refs) < 2:
            raise ValueError("identity value candidate requires two evidence refs")
        if len(self.context_refs) < 2:
            raise ValueError("identity value candidate requires cross-context evidence")

    @property
    def event_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "value_key": self.value_key,
            "event_type": self.event_type.value,
            "value_status": self.value_status.value,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "repeat_count": self.repeat_count,
            "evidence_refs": list(self.evidence_refs),
            "context_refs": list(self.context_refs),
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ValueTrackResult:
    result_id: str
    event: ValueEvent
    observation: TrackObservation
    assessment: ContinuityAssessment
    processed_at: str
    processed_by: str = "runtime:values-track-center"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = VALUE_POLICY_VERSION
    schema_version: str = VALUE_RESULT_VERSION

    def __post_init__(self) -> None:
        if not all((self.result_id, self.processed_at, self.processed_by)):
            raise ValueError("value track result fields must not be empty")
        if self.schema_version != VALUE_RESULT_VERSION:
            raise ValueError(f"unsupported value track result: {self.schema_version}")
        if self.event.value_key != self.observation.subject_id:
            raise ValueError("value event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("value observation and assessment mismatch")
        if self.observation.track != VALUES_TRACK:
            raise ValueError("value result requires canonical values track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "value_registry_mutation_allowed": False,
            "priority_mutation_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_value_observation(event: ValueEvent) -> TrackObservation:
    """Normalize one validated value event into a continuity observation."""

    identity_candidate_statement = None
    identity_scope = None
    identity_repeat_key = None
    if event.event_type in IDENTITY_CANDIDATE_EVENT_TYPES:
        identity_candidate_statement = event.identity_candidate_statement
        identity_scope = event.identity_scope
        identity_repeat_key = event.identity_repeat_key

    observation_payload = {
        "event_id": event.event_id,
        "event_digest": event.event_digest,
        "track": VALUES_TRACK,
        "policy_version": VALUE_POLICY_VERSION,
    }
    observation_id = "value-observation:sha256:" + _digest(observation_payload)

    return TrackObservation(
        observation_id=observation_id,
        track=VALUES_TRACK,
        subject_id=event.value_key,
        entity_status=_entity_status_for_value(event.value_status),
        knowledge_class=event.knowledge_class,
        statement=event.statement,
        occurred_at=event.occurred_at,
        confidence=event.confidence,
        evidence_refs=event.evidence_refs,
        claims_current_intention=event.event_type in CURRENT_VALUE_EVENT_TYPES,
        identity_candidate_statement=identity_candidate_statement,
        identity_scope=identity_scope,
        identity_repeat_key=identity_repeat_key,
        metadata={
            "value_key": event.value_key,
            "value_event_id": event.event_id,
            "value_event_digest": event.event_digest,
            "value_event_type": event.event_type.value,
            "value_status": event.value_status.value,
            "repeat_count": event.repeat_count,
            "context_refs": list(event.context_refs),
            "track_center_policy_version": VALUE_POLICY_VERSION,
            "value_registry_mutation_allowed": False,
            "priority_mutation_allowed": False,
        },
    )


def process_value_event(
    event: ValueEvent,
    *,
    processed_at: str,
    processed_by: str = "runtime:values-track-center",
) -> ValueTrackResult:
    """Process a value event through the center and Continuity Coordinator."""

    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")

    observation = build_value_observation(event)
    assessment = assess_track_observation(
        observation,
        assessed_at=processed_at,
        assessed_by="runtime:continuity-coordinator",
    )
    result_payload = {
        "event_digest": event.event_digest,
        "observation_digest": observation.observation_digest,
        "assessment_id": assessment.assessment_id,
        "policy_version": VALUE_POLICY_VERSION,
    }
    result_id = "value-track-result:sha256:" + _digest(result_payload)

    return ValueTrackResult(
        result_id=result_id,
        event=event,
        observation=observation,
        assessment=assessment,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "handoff": "value_event -> track_observation -> continuity_assessment",
            "single_statement_is_not_a_value": True,
            "cross_context_repetition_required_for_candidate": True,
            "single_event_cannot_modify_stable_identity": True,
            "value_registry_update": "separate_governed_operation",
        },
    )


def _entity_status_for_value(status: ValueStatus) -> EntityStatus:
    if status is ValueStatus.ACTIVE:
        return EntityStatus.ACTIVE
    if status is ValueStatus.CONTESTED:
        return EntityStatus.PAUSED
    if status is ValueStatus.RETIRED:
        return EntityStatus.CLOSED
    return EntityStatus.UNKNOWN


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
