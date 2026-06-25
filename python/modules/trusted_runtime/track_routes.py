"""Typed route adapters for LS track centers."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Union

from .capabilities_constraints_track_center import (
    CAPABILITIES_TRACK,
    CapabilityConstraintEvent,
    CapabilityConstraintResult,
    CapabilityEventType,
    CapabilityStatus,
    process_capability_event,
)
from .capability_contract import ConstraintKind
from .continuity_coordinator import EntityStatus, KnowledgeClass
from .errors_learning_track_center import (
    ERRORS_TRACK,
    ErrorEventType,
    ErrorLearningEvent,
    ErrorLearningResult,
    ErrorStatus,
    OutcomeClass,
    process_error_event,
)
from .goals_commitments_track_center import (
    GOALS_TRACK,
    CommitmentLevel,
    GoalCommitmentEvent,
    GoalCommitmentResult,
    GoalEventType,
    GoalStatus,
    process_goal_event,
)
from .projects_track_center import (
    PROJECTS_TRACK,
    ProjectEvent,
    ProjectEventType,
    ProjectStatus,
    ProjectTrackResult,
    process_project_event,
)
from .relationship_loss_track_center import (
    RELATIONSHIP_LOSS_TRACK,
    RelationshipEventType,
    RelationshipLossEvent,
    RelationshipLossResult,
    process_relationship_event,
)
from .values_track_center import (
    VALUES_TRACK,
    ValueEvent,
    ValueEventType,
    ValueStatus,
    ValueTrackResult,
    process_value_event,
)

SUPPORTED_ROUTES = (
    RELATIONSHIP_LOSS_TRACK,
    PROJECTS_TRACK,
    VALUES_TRACK,
    ERRORS_TRACK,
    GOALS_TRACK,
    CAPABILITIES_TRACK,
)

RoutedTrackResult = Union[
    RelationshipLossResult,
    ProjectTrackResult,
    ValueTrackResult,
    ErrorLearningResult,
    GoalCommitmentResult,
    CapabilityConstraintResult,
]


def dispatch_track_event(
    route: str,
    payload: Mapping[str, Any],
    *,
    processed_at: str,
) -> RoutedTrackResult:
    if route == RELATIONSHIP_LOSS_TRACK:
        return process_relationship_event(
            _relationship_event(payload),
            processed_at=processed_at,
            processed_by="runtime:relationship-loss-track-center",
        )
    if route == PROJECTS_TRACK:
        return process_project_event(
            _project_event(payload),
            processed_at=processed_at,
            processed_by="runtime:projects-track-center",
        )
    if route == VALUES_TRACK:
        return process_value_event(
            _value_event(payload),
            processed_at=processed_at,
            processed_by="runtime:values-track-center",
        )
    if route == ERRORS_TRACK:
        return process_error_event(
            _error_event(payload),
            processed_at=processed_at,
            processed_by="runtime:errors-learning-track-center",
        )
    if route == GOALS_TRACK:
        return process_goal_event(
            _goal_event(payload),
            processed_at=processed_at,
            processed_by="runtime:goals-commitments-track-center",
        )
    if route == CAPABILITIES_TRACK:
        return process_capability_event(
            _capability_event(payload),
            processed_at=processed_at,
            processed_by="runtime:capabilities-constraints-track-center",
        )
    raise ValueError(f"unsupported route: {route}")


def diagnostic_for_route(route: str) -> str:
    return {
        RELATIONSHIP_LOSS_TRACK: "relationship_loss_payload_invalid",
        PROJECTS_TRACK: "project_payload_invalid",
        VALUES_TRACK: "value_payload_invalid",
        ERRORS_TRACK: "error_learning_payload_invalid",
        GOALS_TRACK: "goal_commitment_payload_invalid",
        CAPABILITIES_TRACK: "capability_constraint_payload_invalid",
    }[route]


def _relationship_event(payload: Mapping[str, Any]) -> RelationshipLossEvent:
    return RelationshipLossEvent(
        event_id=str(payload["event_id"]),
        relationship_id=str(payload["relationship_id"]),
        subject_id=str(payload["subject_id"]),
        event_type=RelationshipEventType(str(payload["event_type"])),
        entity_status=EntityStatus(str(payload["entity_status"])),
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "relationship"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.relationship_loss_event.v0.1")),
    )


def _project_event(payload: Mapping[str, Any]) -> ProjectEvent:
    previous = payload.get("previous_status")
    return ProjectEvent(
        event_id=str(payload["event_id"]),
        project_id=str(payload["project_id"]),
        event_type=ProjectEventType(str(payload["event_type"])),
        project_status=ProjectStatus(str(payload["project_status"])),
        previous_status=ProjectStatus(str(previous)) if previous is not None else None,
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "project"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.project_event.v0.1")),
    )


def _value_event(payload: Mapping[str, Any]) -> ValueEvent:
    return ValueEvent(
        event_id=str(payload["event_id"]),
        value_key=str(payload["value_key"]),
        event_type=ValueEventType(str(payload["event_type"])),
        value_status=ValueStatus(str(payload["value_status"])),
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        repeat_count=int(payload["repeat_count"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        context_refs=_refs(payload, "context_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "value"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.value_event.v0.1")),
    )


def _error_event(payload: Mapping[str, Any]) -> ErrorLearningEvent:
    return ErrorLearningEvent(
        event_id=str(payload["event_id"]),
        error_id=str(payload["error_id"]),
        event_type=ErrorEventType(str(payload["event_type"])),
        error_status=ErrorStatus(str(payload["error_status"])),
        outcome_class=OutcomeClass(str(payload["outcome_class"])),
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        occurrence_count=int(payload["occurrence_count"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        context_refs=_refs(payload, "context_refs"),
        observer_refs=_refs(payload, "observer_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "error"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.error_learning_event.v0.1")),
    )


def _goal_event(payload: Mapping[str, Any]) -> GoalCommitmentEvent:
    return GoalCommitmentEvent(
        event_id=str(payload["event_id"]),
        goal_id=str(payload["goal_id"]),
        event_type=GoalEventType(str(payload["event_type"])),
        goal_status=GoalStatus(str(payload["goal_status"])),
        commitment_level=CommitmentLevel(str(payload["commitment_level"])),
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        repeat_count=int(payload["repeat_count"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        context_refs=_refs(payload, "context_refs"),
        commitment_refs=_refs(payload, "commitment_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "goal"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.goal_commitment_event.v0.1")),
    )


def _capability_event(payload: Mapping[str, Any]) -> CapabilityConstraintEvent:
    return CapabilityConstraintEvent(
        event_id=str(payload["event_id"]),
        capability_id=str(payload["capability_id"]),
        event_type=CapabilityEventType(str(payload["event_type"])),
        capability_status=CapabilityStatus(str(payload["capability_status"])),
        constraint_kind=ConstraintKind(str(payload["constraint_kind"])),
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        repeat_count=int(payload["repeat_count"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        context_refs=_refs(payload, "context_refs"),
        observer_refs=_refs(payload, "observer_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "capability"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.capability_constraint_event.v0.1")),
    )


def _refs(payload: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    raw = payload[field_name]
    if isinstance(raw, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence")
    return tuple(str(value) for value in raw)


def _metadata(payload: Mapping[str, Any], kind: str) -> dict[str, Any]:
    raw = payload.get("metadata", {})
    if not isinstance(raw, Mapping):
        raise ValueError(f"{kind} metadata must be a mapping")
    return dict(raw)


def _optional(payload: Mapping[str, Any], field_name: str) -> Optional[str]:
    value = payload.get(field_name)
    return None if value is None else str(value)
