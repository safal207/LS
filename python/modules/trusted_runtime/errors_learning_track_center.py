"""Governed Errors/Learning Track Center for LS.

The center retains failed, unexpected, and near-miss outcomes as inspectable
experience. It may emit only a bounded behavioral lesson after independently
sourced, cross-context recurrence or verified remediation. It never assigns
blame, mutates incident state, schedules remediation, updates stable identity,
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

ERROR_EVENT_VERSION = "trusted_runtime.error_learning_event.v0.1"
ERROR_RESULT_VERSION = "trusted_runtime.error_learning_result.v0.1"
ERROR_POLICY_VERSION = "errors_learning_track_center.v0.1"
ERRORS_TRACK = "errors.learning"


class ErrorStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INVESTIGATING = "INVESTIGATING"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    RESOLVED = "RESOLVED"
    RECURRING = "RECURRING"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class OutcomeClass(str, Enum):
    FAILED = "FAILED"
    UNEXPECTED = "UNEXPECTED"
    NEAR_MISS = "NEAR_MISS"
    CORRECTED = "CORRECTED"
    SUCCESSFUL_REMEDIATION = "SUCCESSFUL_REMEDIATION"


class ErrorEventType(str, Enum):
    ERROR_OBSERVED = "ERROR_OBSERVED"
    FAILURE_VERIFIED = "FAILURE_VERIFIED"
    UNEXPECTED_OUTCOME_RECORDED = "UNEXPECTED_OUTCOME_RECORDED"
    NEAR_MISS_RECORDED = "NEAR_MISS_RECORDED"
    REMEDIATION_APPLIED = "REMEDIATION_APPLIED"
    REMEDIATION_VERIFIED = "REMEDIATION_VERIFIED"
    ERROR_RECURRENCE_CONFIRMED = "ERROR_RECURRENCE_CONFIRMED"
    ATTRIBUTION_DISPUTED = "ATTRIBUTION_DISPUTED"
    ERROR_RESOLVED = "ERROR_RESOLVED"
    ERROR_RETIRED = "ERROR_RETIRED"
    CURRENT_BLAME_CLAIM = "CURRENT_BLAME_CLAIM"


CURRENT_CLAIM_TYPES = frozenset({ErrorEventType.CURRENT_BLAME_CLAIM})
LEARNING_CANDIDATE_TYPES = frozenset(
    {
        ErrorEventType.ERROR_RECURRENCE_CONFIRMED,
        ErrorEventType.REMEDIATION_VERIFIED,
    }
)
SOURCE_BACKED_TYPES = frozenset(
    event_type
    for event_type in ErrorEventType
    if event_type is not ErrorEventType.ERROR_OBSERVED
)


@dataclass(frozen=True)
class ErrorLearningEvent:
    event_id: str
    error_id: str
    event_type: ErrorEventType
    error_status: ErrorStatus
    outcome_class: OutcomeClass
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    occurrence_count: int
    evidence_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    observer_refs: tuple[str, ...]
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ERROR_EVENT_VERSION

    def __post_init__(self) -> None:
        if not all((self.event_id, self.error_id, self.statement, self.occurred_at)):
            raise ValueError("error-learning event fields must not be empty")
        if self.schema_version != ERROR_EVENT_VERSION:
            raise ValueError(f"unsupported error-learning event: {self.schema_version}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("error-learning confidence must be between 0 and 1")
        if self.occurrence_count < 1:
            raise ValueError("occurrence_count must be at least 1")
        _require_unique("evidence_refs", self.evidence_refs)
        _require_unique("context_refs", self.context_refs)
        _require_unique("observer_refs", self.observer_refs)

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
            self._validate_learning_candidate()

        if self.event_type in SOURCE_BACKED_TYPES:
            if self.knowledge_class is not KnowledgeClass.FACT:
                raise ValueError("source-backed error events require FACT knowledge")
            if not self.evidence_refs:
                raise ValueError("source-backed error events require evidence")

        self._validate_event_contract()

    def _validate_learning_candidate(self) -> None:
        if self.event_type not in LEARNING_CANDIDATE_TYPES:
            raise ValueError("this error event type cannot propose a learning lesson")
        if self.identity_scope != ERRORS_TRACK:
            raise ValueError("error learning candidates must use errors.learning scope")
        if self.knowledge_class is not KnowledgeClass.FACT:
            raise ValueError("error learning candidate requires FACT knowledge")
        if self.occurrence_count < 2:
            raise ValueError("error learning candidate requires repeated evidence")
        if len(self.evidence_refs) < 2:
            raise ValueError("error learning candidate requires two evidence refs")
        if len(self.context_refs) < 2:
            raise ValueError("error learning candidate requires cross-context evidence")
        if len(self.observer_refs) < 2:
            raise ValueError("error learning candidate requires observer independence")

        recurrence = self.event_type is ErrorEventType.ERROR_RECURRENCE_CONFIRMED
        remediation = self.event_type is ErrorEventType.REMEDIATION_VERIFIED
        if recurrence and self.error_status is not ErrorStatus.RECURRING:
            raise ValueError("recurrence candidate requires RECURRING status")
        if remediation and self.error_status is not ErrorStatus.RESOLVED:
            raise ValueError("remediation candidate requires RESOLVED status")

    def _validate_event_contract(self) -> None:
        expected_outcomes = {
            ErrorEventType.FAILURE_VERIFIED: OutcomeClass.FAILED,
            ErrorEventType.UNEXPECTED_OUTCOME_RECORDED: OutcomeClass.UNEXPECTED,
            ErrorEventType.NEAR_MISS_RECORDED: OutcomeClass.NEAR_MISS,
            ErrorEventType.REMEDIATION_VERIFIED: OutcomeClass.SUCCESSFUL_REMEDIATION,
        }
        expected = expected_outcomes.get(self.event_type)
        if expected is not None and self.outcome_class is not expected:
            raise ValueError(f"{self.event_type.value} requires {expected.value}")
        required_statuses = {
            ErrorEventType.ATTRIBUTION_DISPUTED: ErrorStatus.DISPUTED,
            ErrorEventType.ERROR_RESOLVED: ErrorStatus.RESOLVED,
            ErrorEventType.ERROR_RETIRED: ErrorStatus.RETIRED,
            ErrorEventType.ERROR_RECURRENCE_CONFIRMED: ErrorStatus.RECURRING,
        }
        required_status = required_statuses.get(self.event_type)
        if required_status is not None and self.error_status is not required_status:
            raise ValueError(
                f"{self.event_type.value} requires {required_status.value} status"
            )
        if self.event_type is ErrorEventType.ERROR_RECURRENCE_CONFIRMED:
            if self.occurrence_count < 2:
                raise ValueError("confirmed recurrence requires occurrence_count >= 2")

    @property
    def event_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "error_id": self.error_id,
            "event_type": self.event_type.value,
            "error_status": self.error_status.value,
            "outcome_class": self.outcome_class.value,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "occurrence_count": self.occurrence_count,
            "evidence_refs": list(self.evidence_refs),
            "context_refs": list(self.context_refs),
            "observer_refs": list(self.observer_refs),
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ErrorLearningResult:
    result_id: str
    event: ErrorLearningEvent
    observation: TrackObservation
    assessment: ContinuityAssessment
    processed_at: str
    processed_by: str = "runtime:errors-learning-track-center"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = ERROR_POLICY_VERSION
    schema_version: str = ERROR_RESULT_VERSION

    def __post_init__(self) -> None:
        if not all((self.result_id, self.processed_at, self.processed_by)):
            raise ValueError("error-learning result fields must not be empty")
        if self.schema_version != ERROR_RESULT_VERSION:
            raise ValueError(f"unsupported error-learning result: {self.schema_version}")
        if self.event.error_id != self.observation.subject_id:
            raise ValueError("error event and observation subject mismatch")
        if self.observation.observation_id != self.assessment.observation_id:
            raise ValueError("error observation and assessment mismatch")
        if self.observation.track != ERRORS_TRACK:
            raise ValueError("error result requires canonical errors track")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "event": self.event.to_dict(),
            "observation": self.observation.to_dict(),
            "assessment": self.assessment.to_dict(),
            "incident_registry_mutation_allowed": False,
            "blame_assignment_allowed": False,
            "remediation_scheduling_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def build_error_observation(event: ErrorLearningEvent) -> TrackObservation:
    candidate = event.event_type in LEARNING_CANDIDATE_TYPES
    observation_id = "error-observation:sha256:" + _digest(
        {
            "event_id": event.event_id,
            "event_digest": event.event_digest,
            "track": ERRORS_TRACK,
            "policy_version": ERROR_POLICY_VERSION,
        }
    )
    return TrackObservation(
        observation_id=observation_id,
        track=ERRORS_TRACK,
        subject_id=event.error_id,
        entity_status=_entity_status(event.error_status),
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
            "error_id": event.error_id,
            "error_event_id": event.event_id,
            "error_event_digest": event.event_digest,
            "error_event_type": event.event_type.value,
            "error_status": event.error_status.value,
            "outcome_class": event.outcome_class.value,
            "occurrence_count": event.occurrence_count,
            "context_refs": list(event.context_refs),
            "observer_refs": list(event.observer_refs),
            "failed_outcome_is_not_success": True,
            "track_center_policy_version": ERROR_POLICY_VERSION,
            "incident_registry_mutation_allowed": False,
            "blame_assignment_allowed": False,
            "remediation_scheduling_allowed": False,
        },
    )


def process_error_event(
    event: ErrorLearningEvent,
    *,
    processed_at: str,
    processed_by: str = "runtime:errors-learning-track-center",
) -> ErrorLearningResult:
    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")
    observation = build_error_observation(event)
    assessment = assess_track_observation(
        observation,
        assessed_at=processed_at,
        assessed_by="runtime:continuity-coordinator",
    )
    result_id = "error-learning-result:sha256:" + _digest(
        {
            "event_digest": event.event_digest,
            "observation_digest": observation.observation_digest,
            "assessment_id": assessment.assessment_id,
            "policy_version": ERROR_POLICY_VERSION,
        }
    )
    return ErrorLearningResult(
        result_id=result_id,
        event=event,
        observation=observation,
        assessment=assessment,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "handoff": "error_event -> track_observation -> continuity_assessment",
            "one_error_is_not_a_trait": True,
            "failed_and_unexpected_are_counterevidence": True,
            "observer_independence_required_for_candidate": True,
            "single_event_cannot_modify_stable_identity": True,
            "incident_update": "separate_governed_operation",
        },
    )


def _entity_status(status: ErrorStatus) -> EntityStatus:
    if status in {ErrorStatus.CONFIRMED, ErrorStatus.RECURRING}:
        return EntityStatus.ACTIVE
    if status in {ErrorStatus.INVESTIGATING, ErrorStatus.DISPUTED}:
        return EntityStatus.PAUSED
    if status in {ErrorStatus.RESOLVED, ErrorStatus.RETIRED}:
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
