"""Verified Episode contracts for governed long-term agent learning.

A verified episode records what was expected, what was observed, and what
bounded lesson may be retained. It never mutates stable agent identity by
itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .contracts import DecisionCode, ReplayDecision
from .orientation import OrientationContext


VERIFIED_EPISODE_VERSION = "trusted_runtime.verified_episode.v0.1"
IDENTITY_UPDATE_POLICY_VERSION = "identity_update.single_episode.v0.1"


class OutcomeStatus(str, Enum):
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"


class CausalStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNVERIFIED = "UNVERIFIED"


class EpisodeStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class VerifiedEpisodeConsistencyError(ValueError):
    """Raised when episode inputs cannot describe one governed transition."""


@dataclass(frozen=True)
class LessonCandidate:
    """A scoped learning candidate, not a global truth or identity mutation."""

    statement: str
    scope: str
    confidence: float
    repeat_key: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.statement, self.scope, self.repeat_key)):
            raise ValueError("lesson statement, scope, and repeat_key must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("lesson confidence must be between 0 and 1")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("lesson evidence_refs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "scope": self.scope,
            "confidence": self.confidence,
            "repeat_key": self.repeat_key,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class IdentityUpdateDecision:
    """Explicitly separates episode storage from stable identity mutation."""

    allowed: bool
    applied: bool
    reason: str
    policy_version: str
    minimum_verified_episodes: int
    current_verified_episodes: int

    def __post_init__(self) -> None:
        if not self.reason or not self.policy_version:
            raise ValueError("identity update reason and policy_version are required")
        if self.minimum_verified_episodes < 2:
            raise ValueError("stable identity updates require multiple episodes")
        if self.current_verified_episodes < 0:
            raise ValueError("current_verified_episodes must be non-negative")
        if self.applied and not self.allowed:
            raise ValueError("identity update cannot be applied when it is not allowed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "applied": self.applied,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "minimum_verified_episodes": self.minimum_verified_episodes,
            "current_verified_episodes": self.current_verified_episodes,
        }


@dataclass(frozen=True)
class VerifiedEpisode:
    """A durable learning record derived from inspected runtime evidence."""

    episode_id: str
    task_id: str
    trail_id: str
    orientation_ref: str
    transition_id: str
    decision: str
    created_at: str
    status: EpisodeStatus
    expected_outcome: Mapping[str, Any]
    observed_outcome: Mapping[str, Any]
    outcome_status: OutcomeStatus
    causal_status: CausalStatus
    replay_status: str
    replay_ref: str
    lesson: LessonCandidate
    identity_update: IdentityUpdateDecision
    source_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = VERIFIED_EPISODE_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != VERIFIED_EPISODE_VERSION:
            raise ValueError(
                f"unsupported verified episode version: {self.schema_version}"
            )
        required = (
            self.episode_id,
            self.task_id,
            self.trail_id,
            self.orientation_ref,
            self.transition_id,
            self.decision,
            self.created_at,
            self.replay_status,
            self.replay_ref,
        )
        if not all(required):
            raise ValueError("verified episode identifiers must not be empty")
        if self.decision not in {item.value for item in DecisionCode}:
            raise ValueError(f"unsupported episode decision: {self.decision}")
        if self.replay_status not in {item.value for item in ReplayDecision}:
            raise ValueError(f"unsupported replay status: {self.replay_status}")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("verified episode source_refs must be unique")
        if self.status is EpisodeStatus.VERIFIED:
            if self.outcome_status is not OutcomeStatus.MATCHED:
                raise ValueError("verified episode requires a matched outcome")
            if self.causal_status is not CausalStatus.VALID:
                raise ValueError("verified episode requires valid causal status")
            if self.replay_status == ReplayDecision.REJECTED.value:
                raise ValueError("verified episode cannot rely on rejected replay")
        if self.identity_update.applied:
            raise ValueError("v0.1 episodes cannot directly mutate stable identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "orientation_ref": self.orientation_ref,
            "transition_id": self.transition_id,
            "decision": self.decision,
            "created_at": self.created_at,
            "status": self.status.value,
            "expected_outcome": dict(self.expected_outcome),
            "observed_outcome": dict(self.observed_outcome),
            "outcome_status": self.outcome_status.value,
            "causal_status": self.causal_status.value,
            "replay_status": self.replay_status,
            "replay_ref": self.replay_ref,
            "lesson": self.lesson.to_dict(),
            "identity_update": self.identity_update.to_dict(),
            "source_refs": list(self.source_refs),
            "metadata": dict(self.metadata),
        }


def build_verified_episode(
    orientation: OrientationContext,
    *,
    replay: Any,
    expected_outcome: Mapping[str, Any],
    observed_outcome: Mapping[str, Any],
    lesson_statement: str,
    lesson_scope: str,
    lesson_confidence: float,
    lesson_repeat_key: str,
    created_at: str,
    causal_status: CausalStatus = CausalStatus.VALID,
    minimum_verified_episodes: int = 3,
    current_verified_episodes: int = 1,
    source_refs: Sequence[str] = (),
    metadata: Optional[Mapping[str, Any]] = None,
    episode_id: Optional[str] = None,
) -> VerifiedEpisode:
    """Build one learning episode from an orientation and replay outcome.

    Expected outcome is a bounded consequence contract. Matching uses expected
    keys only, so observed output may include additional diagnostic fields.
    """

    replay_record = getattr(replay, "record", replay)
    task_id = getattr(replay_record, "task_id", None)
    trail_id = getattr(replay_record, "trail_id", None)
    if (task_id, trail_id) != (orientation.task_id, orientation.trail_id):
        raise VerifiedEpisodeConsistencyError(
            "replay task/trail does not match the orientation context"
        )

    replay_ref = _replay_ref(replay)
    if orientation.replay_ref is None:
        raise VerifiedEpisodeConsistencyError(
            "verified episode requires an orientation replay reference"
        )
    if orientation.replay_ref != replay_ref:
        raise VerifiedEpisodeConsistencyError(
            "orientation replay reference does not match the replay outcome"
        )

    replay_status = _enum_value(getattr(replay_record, "decision", None))
    if replay_status not in {item.value for item in ReplayDecision}:
        raise VerifiedEpisodeConsistencyError(
            f"unsupported replay decision for episode: {replay_status!r}"
        )

    outcome_status = (
        OutcomeStatus.MATCHED
        if _expected_subset_matches(expected_outcome, observed_outcome)
        else OutcomeStatus.MISMATCHED
    )
    episode_status = (
        EpisodeStatus.VERIFIED
        if outcome_status is OutcomeStatus.MATCHED
        and causal_status is CausalStatus.VALID
        and replay_status != ReplayDecision.REJECTED.value
        else EpisodeStatus.UNVERIFIED
    )

    all_source_refs = _unique(
        (
            orientation.orientation_id,
            orientation.transition_id,
            replay_ref,
            *orientation.evidence_refs,
            *source_refs,
        )
    )
    lesson = LessonCandidate(
        statement=lesson_statement,
        scope=lesson_scope,
        confidence=lesson_confidence,
        repeat_key=lesson_repeat_key,
        evidence_refs=tuple(
            ref for ref in all_source_refs if ref in set(orientation.evidence_refs)
        ),
    )
    identity_update = IdentityUpdateDecision(
        allowed=False,
        applied=False,
        reason="single_verified_episode_cannot_modify_stable_identity",
        policy_version=IDENTITY_UPDATE_POLICY_VERSION,
        minimum_verified_episodes=minimum_verified_episodes,
        current_verified_episodes=current_verified_episodes,
    )

    identity_payload = {
        "orientation_ref": orientation.orientation_id,
        "transition_id": orientation.transition_id,
        "decision": orientation.decision,
        "expected_outcome": dict(expected_outcome),
        "observed_outcome": dict(observed_outcome),
        "replay_ref": replay_ref,
        "lesson_repeat_key": lesson_repeat_key,
    }
    stable_episode_id = episode_id or (
        "episode:sha256:" + hashlib.sha256(
            _canonical_json(identity_payload).encode("utf-8")
        ).hexdigest()
    )

    episode_metadata = dict(metadata or {})
    episode_metadata.setdefault("learning_mode", "candidate_only")
    episode_metadata.setdefault("identity_mutation", "separate_governed_decision")

    return VerifiedEpisode(
        episode_id=stable_episode_id,
        task_id=orientation.task_id,
        trail_id=orientation.trail_id,
        orientation_ref=orientation.orientation_id,
        transition_id=orientation.transition_id,
        decision=str(orientation.decision),
        created_at=created_at,
        status=episode_status,
        expected_outcome=dict(expected_outcome),
        observed_outcome=dict(observed_outcome),
        outcome_status=outcome_status,
        causal_status=causal_status,
        replay_status=replay_status,
        replay_ref=replay_ref,
        lesson=lesson,
        identity_update=identity_update,
        source_refs=all_source_refs,
        metadata=episode_metadata,
    )


def _expected_subset_matches(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> bool:
    return all(key in observed and observed[key] == value for key, value in expected.items())


def _replay_ref(replay: Any) -> str:
    report_ref = getattr(replay, "report_ref", None)
    if report_ref:
        return str(report_ref)
    replay_ref = getattr(replay, "replay_ref", None)
    if replay_ref:
        return str(replay_ref)
    replay_id = getattr(getattr(replay, "record", replay), "replay_id", None)
    if replay_id:
        return str(replay_id)
    raise VerifiedEpisodeConsistencyError("replay has no stable reference")


def _enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
