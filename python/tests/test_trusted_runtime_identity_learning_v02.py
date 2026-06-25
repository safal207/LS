from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.identity_learning import (
    AggregationStatus,
    IdentityLearningConsistencyError,
)
from trusted_runtime.identity_learning_v02 import (
    aggregate_verified_episode_v02_mappings,
    verified_episode_v02_view_from_mapping,
)


ROOT = Path(__file__).resolve().parents[2]
AGGREGATION_SCHEMA = (
    ROOT / "schemas/trusted_runtime/lesson_aggregation_v0.2.schema.json"
)
PROPOSAL_SCHEMA = ROOT / "schemas/trusted_runtime/identity_update_proposal.schema.json"
STATEMENT = "Repeated bounded reviews support one stable reviewer preference."
SCOPE = "trusted-pr-review-mvp"
REPEAT_KEY = "reviewer:bounded-evidence-preference"
CREATED_AT = "2026-06-25T12:00:00Z"


def _episode(
    number: int,
    *,
    outcome_class: str = "expected",
    evidence_role: str = "supporting",
    statement: str = STATEMENT,
    confidence: float = 0.8,
    expires_at: str | None = "2026-12-25T00:00:00Z",
    supersedes_episode_id: str | None = None,
) -> dict:
    expected_projection = outcome_class == "expected"
    return {
        "schema_version": "trusted_runtime.verified_episode.v0.2",
        "episode_id": f"episode:sha256:{number:064x}",
        "task_id": f"task:{number}",
        "trail_id": f"trail:{number}",
        "orientation_ref": f"orientation:{number}",
        "transition_id": f"transition:{number}",
        "decision": "ALLOW",
        "created_at": f"2026-06-25T00:{number:02d}:00Z",
        "status": "VERIFIED",
        "outcome_class": outcome_class,
        "expected_state_digest": "sha256:expected-state",
        "verified_state_digest": f"sha256:verified-state-{number}",
        "provenance": {
            "verification_version": "outcome-verification-v0.1",
            "verification_reason_code": {
                "expected": "EXPECTED_OUTCOME_VERIFIED",
                "failed": "FAILURE_OUTCOME_VERIFIED",
                "unexpected": "UNEXPECTED_OUTCOME_VERIFIED",
            }[outcome_class],
            "execution_id": f"exec-{number}",
            "action_id": f"action-{number}",
            "action_digest": f"sha256:action-{number}",
            "actor_id": "agent-a",
            "target_id": "target-1",
            "side_effect_key": "effect-1",
            "receipt_id": f"receipt-{number}",
            "receipt_digest": f"sha256:receipt-{number}",
            "causal_trace_id": f"trace-{number}",
            "observer_evidence_digests": [f"sha256:evidence-{number}"],
            "source_event_ids": [f"event-{number}"],
        },
        "lesson": {
            "statement": statement,
            "scope": SCOPE,
            "confidence": confidence,
            "repeat_key": REPEAT_KEY,
            "evidence_role": evidence_role,
            "evidence_refs": [f"sha256:evidence-{number}"],
        },
        "lifecycle": {
            "retention_class": "bounded",
            "review_after": "2026-07-25T00:00:00Z",
            "expires_at": expires_at,
            "redactable_fields": ["lesson.statement"],
            "redaction_state": "clear",
            "supersedes_episode_id": supersedes_episode_id,
        },
        "experience_eligible": True,
        "identity_update_eligible": False,
        "identity_update": {
            "allowed": False,
            "applied": False,
            "reason": "single_verified_episode_cannot_modify_stable_identity",
            "policy_version": "identity_update.single_episode.v0.2",
            "minimum_verified_episodes": 3,
            "current_verified_episodes": 1,
        },
        "v0_1_projection": {
            "schema_version": "trusted_runtime.verified_episode.v0.1",
            "status": "VERIFIED" if expected_projection else "UNVERIFIED",
            "outcome_status": "MATCHED" if expected_projection else "MISMATCHED",
        },
    }


def _aggregate(episodes):
    return aggregate_verified_episode_v02_mappings(
        episodes,
        scope=SCOPE,
        repeat_key=REPEAT_KEY,
        candidate_statement=STATEMENT,
        created_at=CREATED_AT,
    )


def test_one_supporting_episode_cannot_create_proposal() -> None:
    aggregation = _aggregate((_episode(1),))

    assert aggregation.status is AggregationStatus.INSUFFICIENT_SUPPORT
    assert aggregation.support_count == 1
    assert aggregation.failure_count == 0
    assert aggregation.proposal is None


def test_three_supporting_episodes_create_review_only_proposal() -> None:
    aggregation = _aggregate(
        (
            _episode(1, confidence=0.7),
            _episode(2, confidence=0.8),
            _episode(3, confidence=0.9),
        )
    )

    assert aggregation.status is AggregationStatus.READY_FOR_REVIEW
    assert aggregation.support_count == 3
    assert aggregation.failure_count == 0
    assert aggregation.contradiction_count == 0
    assert aggregation.aggregated_confidence == 0.8
    assert aggregation.proposal is not None
    assert aggregation.proposal.approval_required is True
    assert aggregation.proposal.applied is False

    aggregation_schema = json.loads(AGGREGATION_SCHEMA.read_text(encoding="utf-8"))
    proposal_schema = json.loads(PROPOSAL_SCHEMA.read_text(encoding="utf-8"))
    assert not list(
        Draft202012Validator(aggregation_schema).iter_errors(
            aggregation.to_dict()
        )
    )
    assert not list(
        Draft202012Validator(proposal_schema).iter_errors(
            aggregation.proposal.to_dict()
        )
    )


def test_failure_is_preserved_but_does_not_raise_support_count() -> None:
    failure = _episode(
        3,
        outcome_class="failed",
        evidence_role="failure",
        statement="The bounded review failed and the prior state remained authoritative.",
    )
    aggregation = _aggregate((_episode(1), _episode(2), failure))

    assert aggregation.status is AggregationStatus.INSUFFICIENT_SUPPORT
    assert aggregation.support_count == 2
    assert aggregation.failure_count == 1
    assert aggregation.contradiction_count == 0
    assert aggregation.failure_episode_refs == (failure["episode_id"],)


def test_failure_remains_visible_on_ready_proposal() -> None:
    failure = _episode(
        4,
        outcome_class="failed",
        evidence_role="failure",
        statement="The bounded review failed and the prior state remained authoritative.",
    )
    aggregation = _aggregate(
        (_episode(1), _episode(2), _episode(3), failure)
    )

    assert aggregation.status is AggregationStatus.READY_FOR_REVIEW
    assert aggregation.failure_count == 1
    assert aggregation.proposal is not None
    assert aggregation.proposal.metadata["failure_episode_refs"] == [
        failure["episode_id"]
    ]


def test_contradicting_episode_blocks_proposal_and_lowers_confidence() -> None:
    contradiction = _episode(
        4,
        outcome_class="unexpected",
        evidence_role="contradicting",
        statement="The action produced a different verified state.",
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


def test_failed_v0_1_projection_does_not_make_v0_2_episode_untrusted() -> None:
    failure = _episode(
        2,
        outcome_class="failed",
        evidence_role="failure",
        statement="The bounded review failed and the prior state remained authoritative.",
    )
    assert failure["v0_1_projection"]["status"] == "UNVERIFIED"

    aggregation = _aggregate((_episode(1), failure))

    assert aggregation.failure_count == 1
    assert failure["episode_id"] not in aggregation.ignored_episode_refs
    assert aggregation.metadata["v0_1_projection_is_not_v0_2_trust_status"] is True


def test_duplicate_episode_id_fails_closed() -> None:
    first = _episode(1)

    with pytest.raises(
        IdentityLearningConsistencyError,
        match="duplicate v0.2 episode ID",
    ):
        _aggregate((first, copy.deepcopy(first)))


def test_duplicate_causal_trace_id_fails_closed() -> None:
    first = _episode(1)
    second = _episode(2)
    second["provenance"]["causal_trace_id"] = first["provenance"][
        "causal_trace_id"
    ]

    with pytest.raises(
        IdentityLearningConsistencyError,
        match="duplicate v0.2 causal trace ID",
    ):
        _aggregate((first, second))


def test_expired_episode_is_ignored_for_current_support() -> None:
    expired = _episode(3, expires_at="2026-06-25T11:00:00Z")
    aggregation = _aggregate((_episode(1), _episode(2), expired))

    assert aggregation.status is AggregationStatus.INSUFFICIENT_SUPPORT
    assert aggregation.support_count == 2
    assert aggregation.ignored_count == 1
    assert aggregation.metadata["ignored_reasons"][expired["episode_id"]] == "expired"


def test_superseded_episode_is_ignored_for_current_support() -> None:
    old = _episode(1)
    replacement = _episode(4, supersedes_episode_id=old["episode_id"])
    aggregation = _aggregate((old, _episode(2), _episode(3), replacement))

    assert aggregation.status is AggregationStatus.READY_FOR_REVIEW
    assert aggregation.support_count == 3
    assert aggregation.ignored_count == 1
    assert aggregation.metadata["ignored_reasons"][old["episode_id"]] == "superseded"


def test_outcome_and_evidence_role_mismatch_fails_closed() -> None:
    payload = _episode(
        1,
        outcome_class="failed",
        evidence_role="supporting",
    )

    with pytest.raises(
        IdentityLearningConsistencyError,
        match="outcome_class and lesson.evidence_role are inconsistent",
    ):
        verified_episode_v02_view_from_mapping(payload)
