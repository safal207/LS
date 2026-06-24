"""Deterministic Relationship/Loss Track Center for LS.

This module normalizes bounded relationship and loss events into TrackObservation
records and delegates epistemic safety decisions to the Continuity Coordinator.
It never mutates Relational Self, stable identity, memory, or external state.
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


RELATIONSHIP_LOSS_EVENT_VERSION = "trusted_runtime.relationship_loss_event.v0.1"
RELATIONSHIP_LOSS_RESULT_VERSION = "trusted_runtime.relationship_loss_result.v0.1"
RELATIONSHIP_LOSS_POLICY_VERSION = "relationship_loss_track_center.v0.1"
RELATIONSHIP_LOSS_TRACK = "relationships.loss"


class RelationshipEventType(str, Enum):
    INTERACTION_RECORDED = "INTERACTION_RECORDED"
    RELATIONSHIP_CLOSED = "RELATIONSHIP_CLOSED"
    LOSS_CONFIRMED = "LOSS_CONFIRMED"
    REMEMBERED_INFLUENCE = "REMEMBERED_INFLUENCE"
    CURRENT_PRESENCE_CLAIM = "CURRENT_PRESENCE_CLAIM"
    CURRENT_INTENTION_CLAIM = "CURRENT_INTENTION_CLAIM"


LIFECYCLE_EVENT_TYPES = frozenset(
    {
        RelationshipEventType.INTERACTION_RECORDED,
        RelationshipEventType.RELATIONSHIP_CLOSED,
        RelationshipEventType.LOSS_CONFIRMED,
    }
)

IDENTITY_CANDIDATE_EVENT_TYPES = frozenset(
    {
        RelationshipEventType.INTERACTION_RECORDED,
        RelationshipEventType.REMEMBERED_INFLUENCE,
    }
)


@dataclass(frozen=True)
class RelationshipLossEvent:
    event_id: str
    relationship_id: str
    subject_id: str
    event_type: RelationshipEventType
    entity_status: EntityStatus
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    evidence_refs: tuple[str, ...]
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = RELATIONSHIP_LOSS_EVENT_VERSION

    def __post_init__(self) -> None:
        required = (
            self.event_id,
            self.relationship_id,
            self.subject_id,
            self.statement,
            self.occurred_at,
        )
        if not all(required):
            raise ValueError("relationship/loss event fields must not be empty")
        if self.schema_version != RELATIONSHIP_LOSS_EVENT_VERSION:
            raise ValueError(f"unsupported relationship/loss event: {self.schema_version}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("relationship/loss confidence must be between 0 and 1")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("relationship/loss evidence_refs must be unique")

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
        if has_identity_candidate and self.event_type not in IDENTITY_CANDIDATE_EVENT_TYPES:
            raise ValueError(
                "this relationship/loss event type cannot propose an identity lesson"
            )

        if self.event_type is RelationshipEventType.INTERACTION_RECORDED:
            if self.entity_status is not EntityStatus.ACTIVE:
                raise ValueError("recorded interaction requires ACTIVE entity status")
        elif self.event_type is RelationshipEventType.LOSS_CONFIRMED:
            if self.entity_status is not EntityStatus.DECEASED:
                raise ValueError("confirmed loss requires DECEASED entity status")
        elif self.event_type is RelationshipEventType.RELATIONSHIP_CLOSED:
            if self.entity_status not in {EntityStatus.CLOSED, EntityStatus.DELETED}:
                raise ValueError(
                    "relationship closure requires CLOSED or DELETED entity status"
                )

        if self.event_type in LIFECYCLE_EVENT_TYPES:
            if self.knowledge_class is not KnowledgeClass.FACT:
                raise ValueError("lifecycle relationship events require FACT knowledge")
            if not self.evidence_refs:
                raise ValueError("lifecycle relationship events require evidence")

    @property
    def event_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "relationship_id": self.relationship_id,
            "subject_id": self.subject_id,
            "event_type": self.event_type.value,
            "entity_status": self.entity_status.value,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RelationshipLossResult:
    result_id: str
    event: RelationshipLossEvent
    observation: TrackObservation
    assessment: ContinuityAssessment
    processed_at: str
    processed_by: str = "runtime:relationship-loss-track-center"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = RELATIONSHIP_LOSS_POLICY_VERSION
    schema_version: str = RELATIONSHIP_LOSS_RESULT_VERSION

    def __post_init__(self) -> None:
        if not all((self.result_id, self.processed_at, self.processed_by)):
            raise ValueError("relationship/loss result fields must not be empty")
        if self.schema_version != RELATIONSHIP_LOSS_RESULT_VERSION:
            raise ValueError(f"unsupported relationship/loss result: {self.schema_version}")
        if self.event.subject_id != self.observation.subject_id:
            raise ValueError("event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("observation and continuity assessment mismatch")
        if self.observation.track != RELATIONSHIP_LOSS_TRACK:
            raise ValueError("relationship/loss result requires canonical track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "relational_self_mutation_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_relationship_observation(event: RelationshipLossEvent) -> TrackObservation:
    """Normalize one validated relationship event into a continuity observation."""

    claims_current_presence = (
        event.event_type is RelationshipEventType.CURRENT_PRESENCE_CLAIM
    )
    claims_current_intention = (
        event.event_type is RelationshipEventType.CURRENT_INTENTION_CLAIM
    )

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
        "track": RELATIONSHIP_LOSS_TRACK,
        "policy_version": RELATIONSHIP_LOSS_POLICY_VERSION,
    }
    observation_id = "relationship-observation:sha256:" + _digest(
        observation_payload
    )

    return TrackObservation(
        observation_id=observation_id,
        track=RELATIONSHIP_LOSS_TRACK,
        subject_id=event.subject_id,
        entity_status=event.entity_status,
        knowledge_class=event.knowledge_class,
        statement=event.statement,
        occurred_at=event.occurred_at,
        confidence=event.confidence,
        evidence_refs=event.evidence_refs,
        claims_current_presence=claims_current_presence,
        claims_current_intention=claims_current_intention,
        identity_candidate_statement=identity_candidate_statement,
        identity_scope=identity_scope,
        identity_repeat_key=identity_repeat_key,
        metadata={
            "relationship_id": event.relationship_id,
            "relationship_event_id": event.event_id,
            "relationship_event_digest": event.event_digest,
            "relationship_event_type": event.event_type.value,
            "track_center_policy_version": RELATIONSHIP_LOSS_POLICY_VERSION,
            "relational_self_mutation_allowed": False,
        },
    )


def process_relationship_event(
    event: RelationshipLossEvent,
    *,
    processed_at: str,
    processed_by: str = "runtime:relationship-loss-track-center",
) -> RelationshipLossResult:
    """Process an event through the track center and Continuity Coordinator."""

    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")

    observation = build_relationship_observation(event)
    assessment = assess_track_observation(
        observation,
        assessed_at=processed_at,
        assessed_by="runtime:continuity-coordinator",
    )
    result_payload = {
        "event_digest": event.event_digest,
        "observation_digest": observation.observation_digest,
        "assessment_id": assessment.assessment_id,
        "policy_version": RELATIONSHIP_LOSS_POLICY_VERSION,
    }
    result_id = "relationship-loss-result:sha256:" + _digest(result_payload)

    return RelationshipLossResult(
        result_id=result_id,
        event=event,
        observation=observation,
        assessment=assessment,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "handoff": (
                "relationship_loss_event -> track_observation -> "
                "continuity_assessment"
            ),
            "relational_self_update": "separate_governed_operation",
            "single_event_cannot_modify_stable_identity": True,
            "medical_or_metaphysical_claims_made": False,
        },
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
