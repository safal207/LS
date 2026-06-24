from __future__ import annotations

from types import SimpleNamespace

import pytest

from trusted_runtime.orientation import OrientationContext, OrientationStage
from trusted_runtime.verified_episode import (
    CausalStatus,
    EpisodeStatus,
    IdentityUpdateDecision,
    OutcomeStatus,
    VerifiedEpisodeConsistencyError,
    build_verified_episode,
)


DIMENSIONS = {
    "intent": "declared",
    "authority": "authorized",
    "evidence": "sufficient",
    "risk": "high",
    "reversibility": "compensatable",
    "accountability": "assigned",
}


def _orientation(*, replay_ref: str = "report:1") -> OrientationContext:
    return OrientationContext(
        orientation_id="orientation:1",
        transition_id="transition:1",
        task_id="task:1",
        trail_id="trail:1",
        actor="human:owner",
        intent="Publish one bounded result.",
        created_at="2026-06-24T00:00:00Z",
        stage=OrientationStage.REPLAYABLE,
        role_ids=("reviewer",),
        route_refs=("route:1",),
        evidence_refs=("evidence:diff", "evidence:tests"),
        causal_parent_refs=("event:decision",),
        dimensions=DIMENSIONS,
        decision="ALLOW",
        authorization_ref="authorization:1",
        execution_ref="execution:1",
        effect_ref="effect:1",
        replay_ref=replay_ref,
        artifact_ref="artifact:1",
    )


def _replay(*, decision: str = "ADMISSIBLE", report_ref: str = "report:1"):
    return SimpleNamespace(
        record=SimpleNamespace(
            task_id="task:1",
            trail_id="trail:1",
            replay_id="replay:1",
            decision=decision,
        ),
        report_ref=report_ref,
    )


def _build(**overrides):
    arguments = {
        "replay": _replay(),
        "expected_outcome": {
            "authorization_created": True,
            "protected_effect_count": 1,
        },
        "observed_outcome": {
            "authorization_created": True,
            "protected_effect_count": 1,
            "artifact_created": True,
        },
        "lesson_statement": "Bounded evidence supported one protected effect.",
        "lesson_scope": "trusted-pr-review",
        "lesson_confidence": 0.8,
        "lesson_repeat_key": "trusted-pr-review:allow:bounded-effect",
        "created_at": "2026-06-24T00:10:00Z",
    }
    arguments.update(overrides)
    return build_verified_episode(_orientation(), **arguments)


def test_builds_deterministic_verified_episode_without_identity_mutation() -> None:
    first = _build()
    second = _build()

    assert first.episode_id == second.episode_id
    assert first.status is EpisodeStatus.VERIFIED
    assert first.outcome_status is OutcomeStatus.MATCHED
    assert first.causal_status is CausalStatus.VALID
    assert first.replay_status == "ADMISSIBLE"
    assert first.identity_update.allowed is False
    assert first.identity_update.applied is False
    assert first.identity_update.current_verified_episodes == 1
    assert first.lesson.evidence_refs == ("evidence:diff", "evidence:tests")
    assert first.to_dict()["metadata"]["learning_mode"] == "candidate_only"


def test_mismatched_outcome_is_stored_as_unverified() -> None:
    episode = _build(
        observed_outcome={
            "authorization_created": True,
            "protected_effect_count": 0,
        }
    )

    assert episode.status is EpisodeStatus.UNVERIFIED
    assert episode.outcome_status is OutcomeStatus.MISMATCHED
    assert episode.identity_update.allowed is False


def test_rejected_replay_cannot_produce_verified_episode() -> None:
    episode = _build(replay=_replay(decision="REJECTED"))

    assert episode.status is EpisodeStatus.UNVERIFIED
    assert episode.replay_status == "REJECTED"


def test_replay_reference_must_match_orientation() -> None:
    with pytest.raises(
        VerifiedEpisodeConsistencyError,
        match="replay reference does not match",
    ):
        _build(replay=_replay(report_ref="report:other"))


def test_identity_update_cannot_be_applied_without_permission() -> None:
    with pytest.raises(ValueError, match="cannot be applied"):
        IdentityUpdateDecision(
            allowed=False,
            applied=True,
            reason="invalid",
            policy_version="identity.test.v0.1",
            minimum_verified_episodes=3,
            current_verified_episodes=1,
        )
