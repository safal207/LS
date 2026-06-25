"""Governed Projects Track Center for LS.

The center normalizes explicit project lifecycle and project-intention events
into Continuity Coordinator observations. It preserves lessons from closed
projects without reviving tasks, and never mutates project state, schedules
work, changes stable identity, or authorizes execution.
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


PROJECT_EVENT_VERSION = "trusted_runtime.project_event.v0.1"
PROJECT_RESULT_VERSION = "trusted_runtime.project_track_result.v0.1"
PROJECT_POLICY_VERSION = "projects_track_center.v0.1"
PROJECTS_TRACK = "projects.lifecycle"


class ProjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"
    UNKNOWN = "UNKNOWN"


class ProjectEventType(str, Enum):
    PROJECT_STARTED = "PROJECT_STARTED"
    PROJECT_PAUSED = "PROJECT_PAUSED"
    PROJECT_RESUMED = "PROJECT_RESUMED"
    PROJECT_COMPLETED = "PROJECT_COMPLETED"
    PROJECT_CANCELLED = "PROJECT_CANCELLED"
    PROJECT_ARCHIVED = "PROJECT_ARCHIVED"
    PROJECT_LESSON_RETAINED = "PROJECT_LESSON_RETAINED"
    CURRENT_TASK_CLAIM = "CURRENT_TASK_CLAIM"
    CURRENT_PRIORITY_CLAIM = "CURRENT_PRIORITY_CLAIM"


LIFECYCLE_EVENT_TYPES = frozenset(
    {
        ProjectEventType.PROJECT_STARTED,
        ProjectEventType.PROJECT_PAUSED,
        ProjectEventType.PROJECT_RESUMED,
        ProjectEventType.PROJECT_COMPLETED,
        ProjectEventType.PROJECT_CANCELLED,
        ProjectEventType.PROJECT_ARCHIVED,
    }
)

CURRENT_INTENTION_EVENT_TYPES = frozenset(
    {
        ProjectEventType.CURRENT_TASK_CLAIM,
        ProjectEventType.CURRENT_PRIORITY_CLAIM,
    }
)

IDENTITY_CANDIDATE_EVENT_TYPES = frozenset(
    {ProjectEventType.PROJECT_LESSON_RETAINED}
)

ALLOWED_TRANSITIONS = {
    ProjectEventType.PROJECT_STARTED: {
        (None, ProjectStatus.ACTIVE),
        (ProjectStatus.UNKNOWN, ProjectStatus.ACTIVE),
    },
    ProjectEventType.PROJECT_PAUSED: {
        (ProjectStatus.ACTIVE, ProjectStatus.PAUSED),
    },
    ProjectEventType.PROJECT_RESUMED: {
        (ProjectStatus.PAUSED, ProjectStatus.ACTIVE),
    },
    ProjectEventType.PROJECT_COMPLETED: {
        (ProjectStatus.ACTIVE, ProjectStatus.COMPLETED),
        (ProjectStatus.PAUSED, ProjectStatus.COMPLETED),
    },
    ProjectEventType.PROJECT_CANCELLED: {
        (ProjectStatus.ACTIVE, ProjectStatus.CANCELLED),
        (ProjectStatus.PAUSED, ProjectStatus.CANCELLED),
    },
    ProjectEventType.PROJECT_ARCHIVED: {
        (ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED),
        (ProjectStatus.CANCELLED, ProjectStatus.ARCHIVED),
    },
}


@dataclass(frozen=True)
class ProjectEvent:
    event_id: str
    project_id: str
    event_type: ProjectEventType
    project_status: ProjectStatus
    previous_status: Optional[ProjectStatus]
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    evidence_refs: tuple[str, ...]
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = PROJECT_EVENT_VERSION

    def __post_init__(self) -> None:
        required = (
            self.event_id,
            self.project_id,
            self.statement,
            self.occurred_at,
        )
        if not all(required):
            raise ValueError("project event fields must not be empty")
        if self.schema_version != PROJECT_EVENT_VERSION:
            raise ValueError(f"unsupported project event: {self.schema_version}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("project confidence must be between 0 and 1")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("project evidence_refs must be unique")

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
            raise ValueError("this project event type cannot propose an identity lesson")

        if self.event_type in LIFECYCLE_EVENT_TYPES:
            if self.knowledge_class is not KnowledgeClass.FACT:
                raise ValueError("project lifecycle events require FACT knowledge")
            if not self.evidence_refs:
                raise ValueError("project lifecycle events require evidence")
            transition = (self.previous_status, self.project_status)
            if transition not in ALLOWED_TRANSITIONS[self.event_type]:
                raise ValueError("invalid project lifecycle transition")
        elif self.previous_status is not None:
            raise ValueError("non-lifecycle project events cannot set previous_status")

    @property
    def event_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "project_id": self.project_id,
            "event_type": self.event_type.value,
            "project_status": self.project_status.value,
            "previous_status": (
                self.previous_status.value if self.previous_status else None
            ),
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
class ProjectTrackResult:
    result_id: str
    event: ProjectEvent
    observation: TrackObservation
    assessment: ContinuityAssessment
    processed_at: str
    processed_by: str = "runtime:projects-track-center"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = PROJECT_POLICY_VERSION
    schema_version: str = PROJECT_RESULT_VERSION

    def __post_init__(self) -> None:
        if not all((self.result_id, self.processed_at, self.processed_by)):
            raise ValueError("project track result fields must not be empty")
        if self.schema_version != PROJECT_RESULT_VERSION:
            raise ValueError(f"unsupported project track result: {self.schema_version}")
        if self.event.project_id != self.observation.subject_id:
            raise ValueError("project event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("project observation and assessment mismatch")
        if self.observation.track != PROJECTS_TRACK:
            raise ValueError("project result requires canonical project track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "project_registry_mutation_allowed": False,
            "task_scheduling_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_project_observation(event: ProjectEvent) -> TrackObservation:
    """Normalize one validated project event into a continuity observation."""

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
        "track": PROJECTS_TRACK,
        "policy_version": PROJECT_POLICY_VERSION,
    }
    observation_id = "project-observation:sha256:" + _digest(observation_payload)

    return TrackObservation(
        observation_id=observation_id,
        track=PROJECTS_TRACK,
        subject_id=event.project_id,
        entity_status=_entity_status_for_project(event.project_status),
        knowledge_class=event.knowledge_class,
        statement=event.statement,
        occurred_at=event.occurred_at,
        confidence=event.confidence,
        evidence_refs=event.evidence_refs,
        claims_current_intention=event.event_type in CURRENT_INTENTION_EVENT_TYPES,
        identity_candidate_statement=identity_candidate_statement,
        identity_scope=identity_scope,
        identity_repeat_key=identity_repeat_key,
        metadata={
            "project_id": event.project_id,
            "project_event_id": event.event_id,
            "project_event_digest": event.event_digest,
            "project_event_type": event.event_type.value,
            "project_status": event.project_status.value,
            "previous_status": (
                event.previous_status.value if event.previous_status else None
            ),
            "track_center_policy_version": PROJECT_POLICY_VERSION,
            "project_registry_mutation_allowed": False,
            "task_scheduling_allowed": False,
        },
    )


def process_project_event(
    event: ProjectEvent,
    *,
    processed_at: str,
    processed_by: str = "runtime:projects-track-center",
) -> ProjectTrackResult:
    """Process a project event through the center and Continuity Coordinator."""

    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")

    observation = build_project_observation(event)
    assessment = assess_track_observation(
        observation,
        assessed_at=processed_at,
        assessed_by="runtime:continuity-coordinator",
    )
    result_payload = {
        "event_digest": event.event_digest,
        "observation_digest": observation.observation_digest,
        "assessment_id": assessment.assessment_id,
        "policy_version": PROJECT_POLICY_VERSION,
    }
    result_id = "project-track-result:sha256:" + _digest(result_payload)

    return ProjectTrackResult(
        result_id=result_id,
        event=event,
        observation=observation,
        assessment=assessment,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "handoff": "project_event -> track_observation -> continuity_assessment",
            "closed_project_lessons_do_not_revive_tasks": True,
            "single_event_cannot_modify_stable_identity": True,
            "project_state_update": "separate_governed_operation",
        },
    )


def _entity_status_for_project(status: ProjectStatus) -> EntityStatus:
    if status is ProjectStatus.ACTIVE:
        return EntityStatus.ACTIVE
    if status is ProjectStatus.PAUSED:
        return EntityStatus.PAUSED
    if status in {
        ProjectStatus.COMPLETED,
        ProjectStatus.CANCELLED,
        ProjectStatus.ARCHIVED,
    }:
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
