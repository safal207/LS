from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.identity_learning import (
    AggregationStatus,
    ApprovalState,
    IdentityLearningConsistencyError,
    aggregate_verified_episodes,
    verified_episode_from_mapping,
)
from trusted_runtime.verified_episode import (
    CausalStatus,
    EpisodeStatus,
    IdentityUpdateDecision,
    LessonCandidate,
    OutcomeStatus,
    VerifiedEpisode,
)


ROOT = Path(__file__).resolve().parents[2]
PROPOSAL_SCHEMA = ROOT / "schemas/trusted_runtime/identity_update_proposal.schema.json"
AGGREGATION_SCHEMA = ROOT / "schemas/trusted_runtime/lesson_aggregation.schema.json"
STATEMENT = "Repeated bounded reviews support one stable reviewer preference."
SCOPE = "trusted-pr-review-mvp"
REPEAT_KEY = "reviewer:bounded-evidence-preference"


def _episode(
    number: int,
    *,
    statement: str = STATEMENT,
    confidence: float = 0.8,
    status: EpisodeStatus = EpisodeStatus.VERIFIED,
    replay_status: str = "ADMISSIBLE",
) -> VerifiedEpisode:
    matched = status is EpisodeStatus.VERIFIED
    return VerifiedEpisode(
        episode_id=f"episode:{number}",
        task_id=f"task:{number}",
        trail_id=f"trail:{number}",
        orientation_ref=f"orientation:{number}",
        transition_id=f"transition:{number}",
        decision="ALLOW",
        created_at=f"2026-06-24T00:0{number}:00Z",
        status=status,
        expected_outcome={"effect_count": 1},
        observed_outcome={"effect_count": 1 if matched else 0},
        outcome_status=(
            OutcomeStatus.MATCHED if matched else OutcomeStatus.MISMATCHED
        ),
        causal_status=CausalStatus.VALID,
        replay_status=replay_status,
        replay_ref=f"replay:{number}",
        lesson=LessonCandidate(
            statement=statement,
            scope=SCOPE,
            confidence=confidence,
            repeat_key=REPEAT_KEY,
            evidence_refs=(f"evidence:{number}",),
        ),
        identity_update=IdentityUpdateDecision(
            allowed=False,
            applied=False,
            reason="single_verified_episode_cannot_modify_stable_identity",
            policy_version="identity_update.single_episode.v0.1",
            minimum_verified_episodes=3,
            current_verified_episodes=1,
        ),
        source_refs=(f"orientation:{number}", f"replay:{number}"),
    )


def _aggregate(episodes):
    return aggregate_verified_episodes(
        episodes,
        scope=SCOPE,
        repeat_key=REPEAT_KEY,
        candidate_statement=STATEMENT,
        created_at="2026-06-24T01:00:00Z",
    )


def test_one_episode_cannot_create_identity_proposal() -> None:
    aggregation = _aggregate((_episode(1),))

    assert aggregation.status is AggregationStatus.INSUFFICIENT_SUPPORT
    assert aggregation.support_count == 1
    assert aggregation.proposal is None
    assert aggregation.aggregated_confidence == 0.8


def test_three_matching_verified_episodes_create_review_only_proposal() -> None:
    aggregation = _aggregate(
        (
            _episode(1, confidence=0.7),
            _episode(2, confidence=0.8),
            _episode(3, confidence=0.9),
        )
    )

    assert aggregation.status is AggregationStatus.READY_FOR_REVIEW
    assert aggregation.aggregated_confidence == 0.8
    assert aggregation.proposal is not None
    proposal = aggregation.proposal
    assert proposal.support_count == 3
    assert proposal.approval_required is True
    assert proposal.approval_state is ApprovalState.PENDING
    assert proposal.applied is False
    assert proposal.application_ref is None
    assert proposal.metadata["repetition_is_not_proof"] is True

    proposal_schema = __import__("json").loads(
        PROPOSAL_SCHEMA.read_text(encoding="utf-8")
    )
    aggregation_schema = __import__("json").loads(
        AGGREGATION_SCHEMA.read_text(encoding="utf-8")
    )
    assert not list(
        Draft202012Validator(proposal_schema).iter_errors(proposal.to_dict())
    )
    assert not list(
        Draft202012Validator(aggregation_schema).iter_errors(
            aggregation.to_dict()
        )
    )


def test_verified_contradiction_blocks_proposal_and_lowers_confidence() -> None:
    contradiction = _episode(
        4,
        statement="Repeated bounded reviews do not support that preference.",
        confidence=0.9,
    )
    aggregation = _aggregate(
        (
            _episode(1, confidence=0.8),
            _episode(2, confidence=0.8),
            _episode(3, confidence=0.8),
            contradiction,
        )
    )

    assert aggregation.status is AggregationStatus.CONFLICTED
    assert aggregation.support_count == 3
    assert aggregation.contradiction_count == 1
    assert aggregation.aggregated_confidence == 0.35
    assert aggregation.proposal is None
    assert contradiction.episode_id in aggregation.contradicting_episode_refs


def test_unverified_or_rejected_episode_does_not_count() -> None:
    unverified = _episode(
        4,
        status=EpisodeStatus.UNVERIFIED,
        replay_status="REJECTED",
    )
    aggregation = _aggregate((_episode(1), _episode(2), unverified))

    assert aggregation.status is AggregationStatus.INSUFFICIENT_SUPPORT
    assert aggregation.support_count == 2
    assert aggregation.ignored_count == 1
    assert aggregation.proposal is None


def test_identical_duplicate_episode_is_counted_once() -> None:
    first = _episode(1)
    aggregation = _aggregate((first, first, _episode(2), _episode(3)))

    assert aggregation.status is AggregationStatus.READY_FOR_REVIEW
    assert aggregation.support_count == 3


def test_conflicting_duplicate_episode_id_fails_closed() -> None:
    first = _episode(1)
    conflict = replace(first, lesson=replace(first.lesson, confidence=0.2))

    with pytest.raises(
        IdentityLearningConsistencyError,
        match="conflicting episode payloads",
    ):
        _aggregate((first, conflict))


def test_episode_json_round_trip_preserves_contract() -> None:
    episode = _episode(1)
    restored = verified_episode_from_mapping(episode.to_dict())

    assert restored == episode
