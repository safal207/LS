"""Governed capability observations for LS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .capability_contract import (
    CAPABILITIES_TRACK,
    CURRENT_CLAIM_TYPES,
    LESSON_TYPES,
    CapabilityConstraintEvent,
    CapabilityEventType,
    CapabilityStatus,
    digest,
)
from .continuity_coordinator import (
    ContinuityAssessment,
    EntityStatus,
    TrackObservation,
    assess_track_observation,
)

CAPABILITY_RESULT_VERSION = "trusted_runtime.capability_constraint_result.v0.1"
CAPABILITY_POLICY_VERSION = "capabilities_constraints_track_center.v0.1"
CLOSED_STATUSES = frozenset(
    {
        CapabilityStatus.RECOVERED,
        CapabilityStatus.EXPIRED,
        CapabilityStatus.RETIRED,
    }
)


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
            raise ValueError("capability result fields must not be empty")
        if self.schema_version != CAPABILITY_RESULT_VERSION:
            raise ValueError(f"unsupported capability result: {self.schema_version}")
        if self.event.capability_id != self.observation.subject_id:
            raise ValueError("capability event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("capability observation and assessment mismatch")
        if self.observation.track != CAPABILITIES_TRACK:
            raise ValueError("capability result requires canonical track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "capability_registry_mutation_allowed": False,
            "capability_restriction_allowed": False,
            "global_limitation_assignment_allowed": False,
            "training_scheduling_allowed": False,
            "priority_mutation_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_capability_observation(event: CapabilityConstraintEvent) -> TrackObservation:
    candidate = event.event_type in LESSON_TYPES
    observation_id = "capability-observation:sha256:" + digest(
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
        claims_current_presence=event.event_type in CURRENT_CLAIM_TYPES,
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
            "constraint_kind": event.constraint_kind.value,
            "repeat_count": event.repeat_count,
            "context_refs": list(event.context_refs),
            "observer_refs": list(event.observer_refs),
            "temporary_constraint_is_not_stable_identity": True,
            "local_failure_is_not_global_limitation": True,
            "context_required_for_current_claim": True,
            "track_center_policy_version": CAPABILITY_POLICY_VERSION,
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
    result_id = "capability-constraint-result:sha256:" + digest(
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
            "one_failure_is_not_global_limitation": True,
            "recovery_closes_old_limitation_claim": True,
            "cross_context_repetition_required_for_candidate": True,
            "single_event_cannot_modify_stable_identity": True,
            "capability_update": "separate_governed_operation",
        },
    )


def _entity_status(event: CapabilityConstraintEvent) -> EntityStatus:
    if event.event_type in CURRENT_CLAIM_TYPES and not event.context_refs:
        return EntityStatus.UNKNOWN
    if event.capability_status is CapabilityStatus.DISPUTED:
        return EntityStatus.PAUSED

    if event.event_type is CapabilityEventType.CURRENT_LIMITATION_CLAIM:
        if event.capability_status in CLOSED_STATUSES:
            return EntityStatus.CLOSED
        if event.capability_status in {
            CapabilityStatus.CONSTRAINED,
            CapabilityStatus.UNAVAILABLE,
        }:
            return EntityStatus.ACTIVE
        return EntityStatus.UNKNOWN

    if event.event_type is CapabilityEventType.CURRENT_CAPABILITY_CLAIM:
        if event.capability_status in {
            CapabilityStatus.AVAILABLE,
            CapabilityStatus.RECOVERED,
        }:
            return EntityStatus.ACTIVE
        if event.capability_status is CapabilityStatus.RETIRED:
            return EntityStatus.CLOSED
        if event.capability_status in {
            CapabilityStatus.CONSTRAINED,
            CapabilityStatus.UNAVAILABLE,
        }:
            return EntityStatus.PAUSED
        return EntityStatus.UNKNOWN

    if event.capability_status in {
        CapabilityStatus.AVAILABLE,
        CapabilityStatus.CONSTRAINED,
        CapabilityStatus.UNAVAILABLE,
    }:
        return EntityStatus.ACTIVE
    if event.capability_status in CLOSED_STATUSES:
        return EntityStatus.CLOSED
    if event.capability_status is CapabilityStatus.DISPUTED:
        return EntityStatus.PAUSED
    return EntityStatus.UNKNOWN


__all__ = [
    "CAPABILITIES_TRACK",
    "CapabilityConstraintEvent",
    "CapabilityConstraintResult",
    "CapabilityEventType",
    "CapabilityStatus",
    "process_capability_event",
]
