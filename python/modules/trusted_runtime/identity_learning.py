"""Governed aggregation of Verified Episodes into identity-update proposals.

Repetition may justify a proposal for review. It is never treated as proof and
never applies a stable identity change automatically.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from statistics import mean
from typing import Any, Mapping, Optional, Sequence

from .verified_episode import (
    EpisodeStatus,
    IdentityUpdateDecision,
    LessonCandidate,
    VerifiedEpisode,
)


LESSON_AGGREGATION_VERSION = "trusted_runtime.lesson_aggregation.v0.1"
IDENTITY_UPDATE_PROPOSAL_VERSION = "trusted_runtime.identity_update_proposal.v0.1"
IDENTITY_PROPOSAL_POLICY_VERSION = "identity_update.proposal.v0.1"


class AggregationStatus(str, Enum):
    NO_ELIGIBLE_EPISODES = "NO_ELIGIBLE_EPISODES"
    INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"
    CONFLICTED = "CONFLICTED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"


class ApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class IdentityLearningConsistencyError(ValueError):
    """Raised when episode inputs cannot be aggregated safely."""


@dataclass(frozen=True)
class IdentityUpdateProposal:
    """A reviewable identity hypothesis; never an applied profile mutation."""

    proposal_id: str
    scope: str
    repeat_key: str
    candidate_statement: str
    created_at: str
    aggregated_confidence: float
    support_count: int
    required_support_count: int
    supporting_episode_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    approval_required: bool = True
    approval_state: ApprovalState = ApprovalState.PENDING
    applied: bool = False
    application_ref: Optional[str] = None
    policy_version: str = IDENTITY_PROPOSAL_POLICY_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_UPDATE_PROPOSAL_VERSION

    def __post_init__(self) -> None:
        required = (
            self.proposal_id,
            self.scope,
            self.repeat_key,
            self.candidate_statement,
            self.created_at,
            self.policy_version,
        )
        if not all(required):
            raise ValueError("identity proposal fields must not be empty")
        if self.schema_version != IDENTITY_UPDATE_PROPOSAL_VERSION:
            raise ValueError(
                f"unsupported identity proposal version: {self.schema_version}"
            )
        if self.required_support_count < 3:
            raise ValueError("identity proposal requires at least three episodes")
        if self.support_count < self.required_support_count:
            raise ValueError("identity proposal has insufficient supporting episodes")
        if not 0.0 <= self.aggregated_confidence <= 1.0:
            raise ValueError("aggregated confidence must be between 0 and 1")
        if len(self.supporting_episode_refs) != len(
            set(self.supporting_episode_refs)
        ):
            raise ValueError("supporting episode refs must be unique")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("proposal evidence refs must be unique")
        if not self.approval_required:
            raise ValueError("identity proposal must require separate approval")
        if self.approval_state is not ApprovalState.PENDING:
            raise ValueError("new identity proposal must start in PENDING state")
        if self.applied or self.application_ref is not None:
            raise ValueError("proposal creation cannot apply an identity update")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposal_id": self.proposal_id,
            "scope": self.scope,
            "repeat_key": self.repeat_key,
            "candidate_statement": self.candidate_statement,
            "created_at": self.created_at,
            "aggregated_confidence": self.aggregated_confidence,
            "support_count": self.support_count,
            "required_support_count": self.required_support_count,
            "supporting_episode_refs": list(self.supporting_episode_refs),
            "evidence_refs": list(self.evidence_refs),
            "approval_required": self.approval_required,
            "approval_state": self.approval_state.value,
            "applied": self.applied,
            "application_ref": self.application_ref,
            "policy_version": self.policy_version,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LessonAggregation:
    """Inspectable aggregation result, including why no proposal was emitted."""

    aggregation_id: str
    scope: str
    repeat_key: str
    candidate_statement: str
    created_at: str
    status: AggregationStatus
    supporting_episode_refs: tuple[str, ...]
    contradicting_episode_refs: tuple[str, ...]
    ignored_episode_refs: tuple[str, ...]
    support_count: int
    contradiction_count: int
    ignored_count: int
    aggregated_confidence: float
    required_support_count: int
    proposal: Optional[IdentityUpdateProposal]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = LESSON_AGGREGATION_VERSION

    def __post_init__(self) -> None:
        required = (
            self.aggregation_id,
            self.scope,
            self.repeat_key,
            self.candidate_statement,
            self.created_at,
        )
        if not all(required):
            raise ValueError("lesson aggregation fields must not be empty")
        if self.schema_version != LESSON_AGGREGATION_VERSION:
            raise ValueError(
                f"unsupported lesson aggregation version: {self.schema_version}"
            )
        if self.required_support_count < 3:
            raise ValueError("aggregation requires at least three support episodes")
        if self.support_count != len(self.supporting_episode_refs):
            raise ValueError("support count does not match supporting refs")
        if self.contradiction_count != len(self.contradicting_episode_refs):
            raise ValueError("contradiction count does not match contradicting refs")
        if self.ignored_count != len(self.ignored_episode_refs):
            raise ValueError("ignored count does not match ignored refs")
        all_refs = (
            *self.supporting_episode_refs,
            *self.contradicting_episode_refs,
            *self.ignored_episode_refs,
        )
        if len(all_refs) != len(set(all_refs)):
            raise ValueError("an episode may appear in only one aggregation bucket")
        if not 0.0 <= self.aggregated_confidence <= 1.0:
            raise ValueError("aggregated confidence must be between 0 and 1")
        if self.status is AggregationStatus.READY_FOR_REVIEW:
            if self.proposal is None:
                raise ValueError("ready aggregation requires a proposal")
            if self.contradiction_count:
                raise ValueError("conflicted aggregation cannot be ready")
        elif self.proposal is not None:
            raise ValueError("non-ready aggregation cannot contain a proposal")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "aggregation_id": self.aggregation_id,
            "scope": self.scope,
            "repeat_key": self.repeat_key,
            "candidate_statement": self.candidate_statement,
            "created_at": self.created_at,
            "status": self.status.value,
            "supporting_episode_refs": list(self.supporting_episode_refs),
            "contradicting_episode_refs": list(
                self.contradicting_episode_refs
            ),
            "ignored_episode_refs": list(self.ignored_episode_refs),
            "support_count": self.support_count,
            "contradiction_count": self.contradiction_count,
            "ignored_count": self.ignored_count,
            "aggregated_confidence": self.aggregated_confidence,
            "required_support_count": self.required_support_count,
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "metadata": dict(self.metadata),
        }


def aggregate_verified_episodes(
    episodes: Sequence[VerifiedEpisode],
    *,
    scope: str,
    repeat_key: str,
    candidate_statement: str,
    created_at: str,
    required_support_count: int = 3,
    metadata: Optional[Mapping[str, Any]] = None,
) -> LessonAggregation:
    """Aggregate immutable episodes into a review-only identity proposal.

    Only VERIFIED episodes in the requested scope and repeat key are eligible.
    Exact candidate-statement matches support the proposal. Other verified
    statements under the same key are contradictions and block proposal
    creation. Duplicate episode IDs never count twice.
    """

    if not all((scope, repeat_key, candidate_statement, created_at)):
        raise ValueError("aggregation query fields must not be empty")
    if required_support_count < 3:
        raise ValueError("required_support_count must be at least three")

    unique_episodes = _deduplicate_episodes(episodes)
    supporting: list[VerifiedEpisode] = []
    contradicting: list[VerifiedEpisode] = []
    ignored: list[VerifiedEpisode] = []

    for episode in unique_episodes:
        if (
            episode.status is not EpisodeStatus.VERIFIED
            or episode.lesson.scope != scope
            or episode.lesson.repeat_key != repeat_key
        ):
            ignored.append(episode)
            continue
        if _normalize(episode.lesson.statement) == _normalize(candidate_statement):
            supporting.append(episode)
        else:
            contradicting.append(episode)

    support_confidence = (
        mean(item.lesson.confidence for item in supporting) if supporting else 0.0
    )
    contradiction_confidence = (
        mean(item.lesson.confidence for item in contradicting)
        if contradicting
        else 0.0
    )
    # Repetition does not boost confidence beyond the mean support confidence.
    # Contradictory verified evidence applies a conservative penalty.
    aggregated_confidence = max(
        0.0,
        min(1.0, support_confidence - 0.5 * contradiction_confidence),
    )
    aggregated_confidence = round(aggregated_confidence, 6)

    if not supporting and not contradicting:
        status = AggregationStatus.NO_ELIGIBLE_EPISODES
    elif contradicting:
        status = AggregationStatus.CONFLICTED
    elif len(supporting) < required_support_count:
        status = AggregationStatus.INSUFFICIENT_SUPPORT
    else:
        status = AggregationStatus.READY_FOR_REVIEW

    supporting_refs = tuple(item.episode_id for item in supporting)
    contradicting_refs = tuple(item.episode_id for item in contradicting)
    ignored_refs = tuple(item.episode_id for item in ignored)
    evidence_refs = _unique(
        tuple(
            ref
            for episode in supporting
            for ref in (
                episode.episode_id,
                episode.orientation_ref,
                episode.replay_ref,
                *episode.lesson.evidence_refs,
            )
        )
    )

    proposal: Optional[IdentityUpdateProposal] = None
    if status is AggregationStatus.READY_FOR_REVIEW:
        proposal_payload = {
            "scope": scope,
            "repeat_key": repeat_key,
            "candidate_statement": candidate_statement,
            "supporting_episode_refs": supporting_refs,
            "aggregated_confidence": aggregated_confidence,
            "policy_version": IDENTITY_PROPOSAL_POLICY_VERSION,
        }
        proposal = IdentityUpdateProposal(
            proposal_id="identity-proposal:sha256:"
            + hashlib.sha256(
                _canonical_json(proposal_payload).encode("utf-8")
            ).hexdigest(),
            scope=scope,
            repeat_key=repeat_key,
            candidate_statement=candidate_statement,
            created_at=created_at,
            aggregated_confidence=aggregated_confidence,
            support_count=len(supporting),
            required_support_count=required_support_count,
            supporting_episode_refs=supporting_refs,
            evidence_refs=evidence_refs,
            metadata={
                "operation": "CONSIDER_STABLE_IDENTITY_UPDATE",
                "application": "separate_governed_operation",
                "repetition_is_not_proof": True,
            },
        )

    aggregation_payload = {
        "scope": scope,
        "repeat_key": repeat_key,
        "candidate_statement": candidate_statement,
        "supporting_episode_refs": supporting_refs,
        "contradicting_episode_refs": contradicting_refs,
        "ignored_episode_refs": ignored_refs,
        "status": status.value,
        "required_support_count": required_support_count,
    }
    aggregation_metadata = dict(metadata or {})
    aggregation_metadata.setdefault("contradiction_policy", "BLOCK_PROPOSAL")
    aggregation_metadata.setdefault("confidence_method", "mean_minus_conflict_penalty")
    aggregation_metadata.setdefault("episodes_are_immutable", True)

    return LessonAggregation(
        aggregation_id="lesson-aggregation:sha256:"
        + hashlib.sha256(
            _canonical_json(aggregation_payload).encode("utf-8")
        ).hexdigest(),
        scope=scope,
        repeat_key=repeat_key,
        candidate_statement=candidate_statement,
        created_at=created_at,
        status=status,
        supporting_episode_refs=supporting_refs,
        contradicting_episode_refs=contradicting_refs,
        ignored_episode_refs=ignored_refs,
        support_count=len(supporting),
        contradiction_count=len(contradicting),
        ignored_count=len(ignored),
        aggregated_confidence=aggregated_confidence,
        required_support_count=required_support_count,
        proposal=proposal,
        metadata=aggregation_metadata,
    )


def verified_episode_from_mapping(payload: Mapping[str, Any]) -> VerifiedEpisode:
    """Reconstruct a VerifiedEpisode from its public JSON representation."""

    lesson_payload = payload["lesson"]
    identity_payload = payload["identity_update"]
    return VerifiedEpisode(
        episode_id=str(payload["episode_id"]),
        task_id=str(payload["task_id"]),
        trail_id=str(payload["trail_id"]),
        orientation_ref=str(payload["orientation_ref"]),
        transition_id=str(payload["transition_id"]),
        decision=str(payload["decision"]),
        created_at=str(payload["created_at"]),
        status=EpisodeStatus(str(payload["status"])),
        expected_outcome=dict(payload["expected_outcome"]),
        observed_outcome=dict(payload["observed_outcome"]),
        outcome_status=_enum_from_value(
            "OutcomeStatus", str(payload["outcome_status"])
        ),
        causal_status=_enum_from_value(
            "CausalStatus", str(payload["causal_status"])
        ),
        replay_status=str(payload["replay_status"]),
        replay_ref=str(payload["replay_ref"]),
        lesson=LessonCandidate(
            statement=str(lesson_payload["statement"]),
            scope=str(lesson_payload["scope"]),
            confidence=float(lesson_payload["confidence"]),
            repeat_key=str(lesson_payload["repeat_key"]),
            evidence_refs=tuple(
                str(item) for item in lesson_payload["evidence_refs"]
            ),
        ),
        identity_update=IdentityUpdateDecision(
            allowed=bool(identity_payload["allowed"]),
            applied=bool(identity_payload["applied"]),
            reason=str(identity_payload["reason"]),
            policy_version=str(identity_payload["policy_version"]),
            minimum_verified_episodes=int(
                identity_payload["minimum_verified_episodes"]
            ),
            current_verified_episodes=int(
                identity_payload["current_verified_episodes"]
            ),
        ),
        source_refs=tuple(str(item) for item in payload["source_refs"]),
        metadata=dict(payload["metadata"]),
        schema_version=str(payload["schema_version"]),
    )


def _enum_from_value(enum_name: str, value: str) -> Any:
    # Local import avoids broadening the public aggregation imports.
    from .verified_episode import CausalStatus, OutcomeStatus

    enums = {"CausalStatus": CausalStatus, "OutcomeStatus": OutcomeStatus}
    return enums[enum_name](value)


def _deduplicate_episodes(
    episodes: Sequence[VerifiedEpisode],
) -> tuple[VerifiedEpisode, ...]:
    by_id: dict[str, VerifiedEpisode] = {}
    for episode in episodes:
        existing = by_id.get(episode.episode_id)
        if existing is None:
            by_id[episode.episode_id] = episode
            continue
        if existing.to_dict() != episode.to_dict():
            raise IdentityLearningConsistencyError(
                f"conflicting episode payloads share ID {episode.episode_id!r}"
            )
    return tuple(by_id.values())


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
