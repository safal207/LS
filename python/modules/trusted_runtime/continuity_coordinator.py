"""Fail-closed continuity coordination above LS track centers.

The coordinator converts one track-center observation into an inspectable
continuity assessment. It may preserve historical influence and emit a bounded
LessonCandidate, but it never creates current presence for an absent entity,
never authorizes execution, and never applies a stable identity update.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from .verified_episode import LessonCandidate


CONTINUITY_ASSESSMENT_VERSION = "trusted_runtime.continuity_assessment.v0.1"
CONTINUITY_POLICY_VERSION = "continuity_coordinator.v0.1"


class EntityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DECEASED = "DECEASED"
    CLOSED = "CLOSED"
    DELETED = "DELETED"
    UNKNOWN = "UNKNOWN"


class KnowledgeClass(str, Enum):
    FACT = "FACT"
    MEMORY = "MEMORY"
    INFERENCE = "INFERENCE"
    SYMBOLIC_MEANING = "SYMBOLIC_MEANING"


class ContinuityDecision(str, Enum):
    ACCEPT_BOUNDED_OBSERVATION = "ACCEPT_BOUNDED_OBSERVATION"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
    BLOCK_FALSE_PRESENCE = "BLOCK_FALSE_PRESENCE"


class ContinuityReason(str, Enum):
    VERIFIED_CURRENT_CLAIM = "VERIFIED_CURRENT_CLAIM"
    UNVERIFIED_CURRENT_CLAIM = "UNVERIFIED_CURRENT_CLAIM"
    FALSE_CURRENT_PRESENCE = "FALSE_CURRENT_PRESENCE"
    FALSE_CURRENT_INTENTION = "FALSE_CURRENT_INTENTION"
    ENTITY_STATUS_UNKNOWN = "ENTITY_STATUS_UNKNOWN"
    ENTITY_TEMPORARILY_INACTIVE = "ENTITY_TEMPORARILY_INACTIVE"
    HISTORICAL_INFLUENCE_PRESERVED = "HISTORICAL_INFLUENCE_PRESERVED"
    BOUNDED_LESSON_ONLY = "BOUNDED_LESSON_ONLY"
    NO_IDENTITY_CANDIDATE = "NO_IDENTITY_CANDIDATE"


IRREVERSIBLY_INACTIVE_STATUSES = frozenset(
    {
        EntityStatus.DECEASED,
        EntityStatus.CLOSED,
        EntityStatus.DELETED,
    }
)

TEMPORARILY_INACTIVE_STATUSES = frozenset({EntityStatus.PAUSED})


@dataclass(frozen=True)
class TrackObservation:
    observation_id: str
    track: str
    subject_id: str
    entity_status: EntityStatus
    knowledge_class: KnowledgeClass
    statement: str
    occurred_at: str
    confidence: float
    evidence_refs: tuple[str, ...]
    claims_current_presence: bool = False
    claims_current_intention: bool = False
    identity_candidate_statement: Optional[str] = None
    identity_scope: Optional[str] = None
    identity_repeat_key: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = (
            self.observation_id,
            self.track,
            self.subject_id,
            self.statement,
            self.occurred_at,
        )
        if not all(required):
            raise ValueError("track observation fields must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("observation confidence must be between 0 and 1")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("observation evidence_refs must be unique")

        identity_fields = (
            self.identity_candidate_statement,
            self.identity_scope,
            self.identity_repeat_key,
        )
        has_any_identity_field = any(value is not None for value in identity_fields)
        if has_any_identity_field and not all(identity_fields):
            raise ValueError(
                "identity candidate statement, scope, and repeat_key "
                "must be set together"
            )

    @property
    def observation_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "track": self.track,
            "subject_id": self.subject_id,
            "entity_status": self.entity_status.value,
            "knowledge_class": self.knowledge_class.value,
            "statement": self.statement,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "claims_current_presence": self.claims_current_presence,
            "claims_current_intention": self.claims_current_intention,
            "identity_candidate_statement": self.identity_candidate_statement,
            "identity_scope": self.identity_scope,
            "identity_repeat_key": self.identity_repeat_key,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ContinuityAssessment:
    assessment_id: str
    observation_id: str
    observation_digest: str
    subject_id: str
    track: str
    entity_status: EntityStatus
    knowledge_class: KnowledgeClass
    decision: ContinuityDecision
    reason_codes: tuple[ContinuityReason, ...]
    normalized_statement: str
    preserved_influence: Optional[str]
    lesson_candidate: Optional[LessonCandidate]
    source_refs: tuple[str, ...]
    assessed_at: str
    assessed_by: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = CONTINUITY_POLICY_VERSION
    schema_version: str = CONTINUITY_ASSESSMENT_VERSION

    def __post_init__(self) -> None:
        required = (
            self.assessment_id,
            self.observation_id,
            self.observation_digest,
            self.subject_id,
            self.track,
            self.normalized_statement,
            self.assessed_at,
            self.assessed_by,
            self.policy_version,
        )
        if not all(required):
            raise ValueError("continuity assessment fields must not be empty")
        if self.schema_version != CONTINUITY_ASSESSMENT_VERSION:
            raise ValueError(f"unsupported assessment version: {self.schema_version}")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("continuity reason codes must be unique")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("continuity source_refs must be unique")
        if self.decision is not ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION:
            if self.lesson_candidate is not None:
                raise ValueError("held or blocked observations cannot emit lessons")
        if self.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE:
            if self.entity_status not in IRREVERSIBLY_INACTIVE_STATUSES:
                raise ValueError("false-presence block requires an inactive entity")
            if self.preserved_influence is None:
                raise ValueError(
                    "false-presence block must preserve historical influence"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assessment_id": self.assessment_id,
            "observation_id": self.observation_id,
            "observation_digest": self.observation_digest,
            "subject_id": self.subject_id,
            "track": self.track,
            "entity_status": self.entity_status.value,
            "knowledge_class": self.knowledge_class.value,
            "decision": self.decision.value,
            "reason_codes": [reason.value for reason in self.reason_codes],
            "normalized_statement": self.normalized_statement,
            "preserved_influence": self.preserved_influence,
            "lesson_candidate": (
                self.lesson_candidate.to_dict() if self.lesson_candidate else None
            ),
            "source_refs": list(self.source_refs),
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "assessed_at": self.assessed_at,
            "assessed_by": self.assessed_by,
            "metadata": dict(self.metadata),
        }


def assess_track_observation(
    observation: TrackObservation,
    *,
    assessed_at: str,
    assessed_by: str = "runtime:continuity-coordinator",
) -> ContinuityAssessment:
    """Evaluate one observation without fabricating presence or mutating identity."""

    if not assessed_at or not assessed_by:
        raise ValueError("assessed_at and assessed_by are required")

    inactive = observation.entity_status in IRREVERSIBLY_INACTIVE_STATUSES
    temporarily_inactive = (
        observation.entity_status in TEMPORARILY_INACTIVE_STATUSES
    )
    current_claim = (
        observation.claims_current_presence or observation.claims_current_intention
    )
    false_presence = inactive and observation.claims_current_presence
    false_intention = inactive and observation.claims_current_intention

    reason_codes: list[ContinuityReason] = []
    lesson_candidate: Optional[LessonCandidate] = None
    preserved_influence: Optional[str] = None

    if false_presence or false_intention:
        decision = ContinuityDecision.BLOCK_FALSE_PRESENCE
        if false_presence:
            reason_codes.append(ContinuityReason.FALSE_CURRENT_PRESENCE)
        if false_intention:
            reason_codes.append(ContinuityReason.FALSE_CURRENT_INTENTION)
        reason_codes.append(ContinuityReason.HISTORICAL_INFLUENCE_PRESERVED)
        preserved_influence = observation.statement
        normalized_statement = (
            "Historical influence may be retained, but no current presence or "
            "new intention is established."
        )
    elif current_claim and temporarily_inactive:
        decision = ContinuityDecision.HOLD_FOR_REVIEW
        reason_codes.append(ContinuityReason.ENTITY_TEMPORARILY_INACTIVE)
        normalized_statement = (
            "The entity is temporarily inactive; current presence or intention "
            "cannot enter the identity-learning path until reactivation is verified."
        )
    elif current_claim and (
        observation.entity_status is EntityStatus.UNKNOWN
        or observation.knowledge_class is not KnowledgeClass.FACT
        or not observation.evidence_refs
    ):
        decision = ContinuityDecision.HOLD_FOR_REVIEW
        if observation.entity_status is EntityStatus.UNKNOWN:
            reason_codes.append(ContinuityReason.ENTITY_STATUS_UNKNOWN)
        reason_codes.append(ContinuityReason.UNVERIFIED_CURRENT_CLAIM)
        normalized_statement = (
            "Current presence or intention remains unverified and cannot enter "
            "the identity-learning path."
        )
    else:
        decision = ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
        normalized_statement = observation.statement
        if current_claim:
            reason_codes.append(ContinuityReason.VERIFIED_CURRENT_CLAIM)
        if inactive:
            preserved_influence = observation.statement
            reason_codes.append(ContinuityReason.HISTORICAL_INFLUENCE_PRESERVED)

        if observation.identity_candidate_statement is None:
            reason_codes.append(ContinuityReason.NO_IDENTITY_CANDIDATE)
        else:
            lesson_candidate = LessonCandidate(
                statement=observation.identity_candidate_statement,
                scope=observation.identity_scope or "",
                confidence=observation.confidence,
                repeat_key=observation.identity_repeat_key or "",
                evidence_refs=observation.evidence_refs,
            )
            reason_codes.append(ContinuityReason.BOUNDED_LESSON_ONLY)

    payload = {
        "observation_id": observation.observation_id,
        "observation_digest": observation.observation_digest,
        "decision": decision.value,
        "reason_codes": [reason.value for reason in reason_codes],
        "policy_version": CONTINUITY_POLICY_VERSION,
    }
    assessment_id = "continuity-assessment:sha256:" + _digest(payload)
    source_refs = _unique((observation.observation_id, *observation.evidence_refs))

    return ContinuityAssessment(
        assessment_id=assessment_id,
        observation_id=observation.observation_id,
        observation_digest=observation.observation_digest,
        subject_id=observation.subject_id,
        track=observation.track,
        entity_status=observation.entity_status,
        knowledge_class=observation.knowledge_class,
        decision=decision,
        reason_codes=tuple(reason_codes),
        normalized_statement=normalized_statement,
        preserved_influence=preserved_influence,
        lesson_candidate=lesson_candidate,
        source_refs=source_refs,
        assessed_at=assessed_at,
        assessed_by=assessed_by,
        metadata={
            "identity_pipeline": (
                "continuity_assessment -> verified_episode -> aggregation -> "
                "independent_approval -> committed_patch"
            ),
            "memory_is_not_presence": True,
            "temporarily_inactive_requires_verified_reactivation": True,
            "single_observation_cannot_modify_stable_identity": True,
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


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
