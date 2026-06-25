"""Governed Goals/Commitments Track Center for LS.

The center separates wishes, intentions, plans, commitments, and obligations.
It may emit only a bounded LessonCandidate after repeated, cross-context,
source-backed follow-through or verified release. It never mutates goal state,
assigns obligation, schedules work, reorders priorities, updates stable identity,
or authorizes execution.
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

GOAL_EVENT_VERSION = "trusted_runtime.goal_commitment_event.v0.1"
GOAL_RESULT_VERSION = "trusted_runtime.goal_commitment_result.v0.1"
GOAL_POLICY_VERSION = "goals_commitments_track_center.v0.1"
GOALS_TRACK = "goals.commitments"


class GoalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISPUTED = "DISPUTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class CommitmentLevel(str, Enum):
    WISH = "WISH"
    INTENTION = "INTENTION"
    PLAN = "PLAN"
    COMMITMENT = "COMMITMENT"
    OBLIGATION = "OBLIGATION"


class GoalEventType(str, Enum):
    WISH_OBSERVED = "WISH_OBSERVED"
    INTENTION_STATED = "INTENTION_STATED"
    PLAN_RECORDED = "PLAN_RECORDED"
    COMMITMENT_DECLARED = "COMMITMENT_DECLARED"
    COMMITMENT_REAFFIRMED = "COMMITMENT_REAFFIRMED"
    OBLIGATION_ACCEPTED = "OBLIGATION_ACCEPTED"
    FOLLOW_THROUGH_VERIFIED = "FOLLOW_THROUGH_VERIFIED"
    COMMITMENT_PAUSED = "COMMITMENT_PAUSED"
    COMMITMENT_COMPLETED = "COMMITMENT_COMPLETED"
    COMMITMENT_CANCELLED = "COMMITMENT_CANCELLED"
    COMMITMENT_EXPIRED = "COMMITMENT_EXPIRED"
    COMMITMENT_RETIRED = "COMMITMENT_RETIRED"
    COMMITMENT_RELEASE_VERIFIED = "COMMITMENT_RELEASE_VERIFIED"
    CURRENT_DUTY_CLAIM = "CURRENT_DUTY_CLAIM"


DUTY_LEVELS = frozenset(
    {CommitmentLevel.COMMITMENT, CommitmentLevel.OBLIGATION}
)
CURRENT_DUTY_EVENT_TYPES = frozenset({GoalEventType.CURRENT_DUTY_CLAIM})
LESSON_CANDIDATE_EVENT_TYPES = frozenset(
    {
        GoalEventType.FOLLOW_THROUGH_VERIFIED,
        GoalEventType.COMMITMENT_RELEASE_VERIFIED,
    }
)
SOURCE_BACKED_EVENT_TYPES = frozenset(
    {
        GoalEventType.COMMITMENT_DECLARED,
        GoalEventType.COMMITMENT_REAFFIRMED,
        GoalEventType.OBLIGATION_ACCEPTED,
        GoalEventType.FOLLOW_THROUGH_VERIFIED,
        GoalEventType.COMMITMENT_PAUSED,
        GoalEventType.COMMITMENT_COMPLETED,
        GoalEventType.COMMITMENT_CANCELLED,
        GoalEventType.COMMITMENT_EXPIRED,
        GoalEventType.COMMITMENT_RETIRED,
        GoalEventType.COMMITMENT_RELEASE_VERIFIED,
        GoalEventType.CURRENT_DUTY_CLAIM,
    }
)
CLOSED_STATUSES = frozenset(
    {
        GoalStatus.COMPLETED,
        GoalStatus.CANCELLED,
        GoalStatus.EXPIRED,
        GoalStatus.RETIRED,
    }
)
RELEASE_STATUSES = frozenset(
    {GoalStatus.CANCELLED, GoalStatus.EXPIRED, GoalStatus.RETIRED}
)


@dataclass(frozen=True)
class GoalCommitmentEvent:
    event_id: str
    goal_id: str
    event_type: GoalEventType
    goal_status: GoalStatus
    commitment_level: CommitmentLevel
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    repeat_count: int
    evidence_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    commitment_refs: tuple[str, ...]
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = GOAL_EVENT_VERSION

    def __post_init__(self) -> None:
        if not all((self.event_id, self.goal_id, self.statement, self.occurred_at)):
            raise ValueError("goal commitment event fields must not be empty")
        if self.schema_version != GOAL_EVENT_VERSION:
            raise ValueError(f"unsupported goal commitment event: {self.schema_version}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("goal confidence must be between 0 and 1")
        if self.repeat_count < 1:
            raise ValueError("goal repeat_count must be at least 1")
        _require_unique("evidence_refs", self.evidence_refs)
        _require_unique("context_refs", self.context_refs)
        _require_unique("commitment_refs", self.commitment_refs)

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
                raise ValueError("source-backed goal events require FACT knowledge")
            if not self.evidence_refs:
                raise ValueError("source-backed goal events require evidence")

        self._validate_event_contract()

    def _validate_lesson_candidate(self) -> None:
        if self.event_type not in LESSON_CANDIDATE_EVENT_TYPES:
            raise ValueError("this goal event type cannot propose an identity lesson")
        if self.identity_scope != GOALS_TRACK:
            raise ValueError("goal lesson candidates must use goals.commitments scope")
        if self.knowledge_class is not KnowledgeClass.FACT:
            raise ValueError("goal lesson candidate requires FACT knowledge")
        if self.repeat_count < 2:
            raise ValueError("goal lesson candidate requires repeated evidence")
        if len(self.evidence_refs) < 2:
            raise ValueError("goal lesson candidate requires two evidence refs")
        if len(self.context_refs) < 2:
            raise ValueError("goal lesson candidate requires cross-context evidence")
        if len(self.commitment_refs) < 2:
            raise ValueError("goal lesson candidate requires distinct commitments")
        if self.commitment_level not in DUTY_LEVELS:
            raise ValueError("goal lesson candidate requires commitment or obligation")

        if self.event_type is GoalEventType.FOLLOW_THROUGH_VERIFIED:
            if self.goal_status is not GoalStatus.COMPLETED:
                raise ValueError("follow-through candidate requires COMPLETED status")
        elif self.goal_status not in RELEASE_STATUSES:
            raise ValueError("release candidate requires a released goal status")

    def _validate_event_contract(self) -> None:
        level_by_event = {
            GoalEventType.WISH_OBSERVED: CommitmentLevel.WISH,
            GoalEventType.INTENTION_STATED: CommitmentLevel.INTENTION,
            GoalEventType.PLAN_RECORDED: CommitmentLevel.PLAN,
            GoalEventType.OBLIGATION_ACCEPTED: CommitmentLevel.OBLIGATION,
        }
        required_level = level_by_event.get(self.event_type)
        if required_level is not None and self.commitment_level is not required_level:
            raise ValueError(
                f"{self.event_type.value} requires {required_level.value} level"
            )

        if self.event_type in {
            GoalEventType.COMMITMENT_DECLARED,
            GoalEventType.COMMITMENT_REAFFIRMED,
        }:
            if self.commitment_level is not CommitmentLevel.COMMITMENT:
                raise ValueError("commitment events require COMMITMENT level")
            if self.goal_status is not GoalStatus.ACTIVE:
                raise ValueError("commitment events require ACTIVE status")

        status_by_event = {
            GoalEventType.COMMITMENT_PAUSED: GoalStatus.PAUSED,
            GoalEventType.COMMITMENT_COMPLETED: GoalStatus.COMPLETED,
            GoalEventType.COMMITMENT_CANCELLED: GoalStatus.CANCELLED,
            GoalEventType.COMMITMENT_EXPIRED: GoalStatus.EXPIRED,
            GoalEventType.COMMITMENT_RETIRED: GoalStatus.RETIRED,
            GoalEventType.FOLLOW_THROUGH_VERIFIED: GoalStatus.COMPLETED,
        }
        required_status = status_by_event.get(self.event_type)
        if required_status is not None and self.goal_status is not required_status:
            raise ValueError(
                f"{self.event_type.value} requires {required_status.value} status"
            )

        if self.event_type is GoalEventType.COMMITMENT_RELEASE_VERIFIED:
            if self.goal_status not in RELEASE_STATUSES:
                raise ValueError("release verification requires released status")

        if self.event_type is GoalEventType.CURRENT_DUTY_CLAIM:
            if self.commitment_level not in DUTY_LEVELS:
                raise ValueError("current duty claim requires commitment or obligation")

    @property
    def event_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "goal_id": self.goal_id,
            "event_type": self.event_type.value,
            "goal_status": self.goal_status.value,
            "commitment_level": self.commitment_level.value,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "repeat_count": self.repeat_count,
            "evidence_refs": list(self.evidence_refs),
            "context_refs": list(self.context_refs),
            "commitment_refs": list(self.commitment_refs),
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GoalCommitmentResult:
    result_id: str
    event: GoalCommitmentEvent
    observation: TrackObservation
    assessment: ContinuityAssessment
    processed_at: str
    processed_by: str = "runtime:goals-commitments-track-center"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = GOAL_POLICY_VERSION
    schema_version: str = GOAL_RESULT_VERSION

    def __post_init__(self) -> None:
        if not all((self.result_id, self.processed_at, self.processed_by)):
            raise ValueError("goal commitment result fields must not be empty")
        if self.schema_version != GOAL_RESULT_VERSION:
            raise ValueError(f"unsupported goal commitment result: {self.schema_version}")
        if self.event.goal_id != self.observation.subject_id:
            raise ValueError("goal event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("goal observation and assessment mismatch")
        if self.observation.track != GOALS_TRACK:
            raise ValueError("goal result requires canonical goals track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "goal_registry_mutation_allowed": False,
            "obligation_assignment_allowed": False,
            "work_scheduling_allowed": False,
            "priority_mutation_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_goal_observation(event: GoalCommitmentEvent) -> TrackObservation:
    candidate = event.event_type in LESSON_CANDIDATE_EVENT_TYPES
    observation_id = "goal-observation:sha256:" + _digest(
        {
            "event_id": event.event_id,
            "event_digest": event.event_digest,
            "track": GOALS_TRACK,
            "policy_version": GOAL_POLICY_VERSION,
        }
    )
    return TrackObservation(
        observation_id=observation_id,
        track=GOALS_TRACK,
        subject_id=event.goal_id,
        entity_status=_entity_status(event.goal_status),
        knowledge_class=event.knowledge_class,
        statement=event.statement,
        occurred_at=event.occurred_at,
        confidence=event.confidence,
        evidence_refs=event.evidence_refs,
        claims_current_intention=event.event_type in CURRENT_DUTY_EVENT_TYPES,
        identity_candidate_statement=(
            event.identity_candidate_statement if candidate else None
        ),
        identity_scope=event.identity_scope if candidate else None,
        identity_repeat_key=event.identity_repeat_key if candidate else None,
        metadata={
            "goal_id": event.goal_id,
            "goal_event_id": event.event_id,
            "goal_event_digest": event.event_digest,
            "goal_event_type": event.event_type.value,
            "goal_status": event.goal_status.value,
            "commitment_level": event.commitment_level.value,
            "repeat_count": event.repeat_count,
            "context_refs": list(event.context_refs),
            "commitment_refs": list(event.commitment_refs),
            "wish_is_not_commitment": True,
            "closed_goal_is_not_current_debt": True,
            "track_center_policy_version": GOAL_POLICY_VERSION,
            "goal_registry_mutation_allowed": False,
            "obligation_assignment_allowed": False,
            "work_scheduling_allowed": False,
            "priority_mutation_allowed": False,
        },
    )


def process_goal_event(
    event: GoalCommitmentEvent,
    *,
    processed_at: str,
    processed_by: str = "runtime:goals-commitments-track-center",
) -> GoalCommitmentResult:
    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")
    observation = build_goal_observation(event)
    assessment = assess_track_observation(
        observation,
        assessed_at=processed_at,
        assessed_by="runtime:continuity-coordinator",
    )
    result_id = "goal-commitment-result:sha256:" + _digest(
        {
            "event_digest": event.event_digest,
            "observation_digest": observation.observation_digest,
            "assessment_id": assessment.assessment_id,
            "policy_version": GOAL_POLICY_VERSION,
        }
    )
    return GoalCommitmentResult(
        result_id=result_id,
        event=event,
        observation=observation,
        assessment=assessment,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "handoff": "goal_event -> track_observation -> continuity_assessment",
            "wish_plan_and_commitment_are_distinct": True,
            "cancelled_goal_is_not_permanent_debt": True,
            "cross_context_repetition_required_for_candidate": True,
            "single_event_cannot_modify_stable_identity": True,
            "goal_update": "separate_governed_operation",
        },
    )


def _entity_status(status: GoalStatus) -> EntityStatus:
    if status is GoalStatus.ACTIVE:
        return EntityStatus.ACTIVE
    if status in {GoalStatus.PAUSED, GoalStatus.DISPUTED}:
        return EntityStatus.PAUSED
    if status in CLOSED_STATUSES:
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
