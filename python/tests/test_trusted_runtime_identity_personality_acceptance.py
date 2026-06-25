from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.agent_personality_projection import (
    ProjectionValidity,
    validate_personality_projection,
)
from trusted_runtime.identity_governance import (
    IdentityAlreadyAppliedError,
    activate_identity_profile_patch,
    rollback_identity_application,
)
from trusted_runtime.identity_learning import AggregationStatus
from trusted_runtime.identity_learning_v02 import (
    aggregate_verified_episode_v02_mappings,
)
from trusted_runtime.identity_personality_acceptance import (
    DEFAULT_REPEAT_KEY,
    DEFAULT_SCOPE,
    DEFAULT_STATEMENT,
    DEFAULT_TRAIT_KEY,
    build_verified_episode_v02,
    run_identity_personality_acceptance,
)


ROOT = Path(__file__).resolve().parents[2]
AGGREGATION_SCHEMA = (
    ROOT / "schemas/trusted_runtime/lesson_aggregation_v0.2.schema.json"
)
PROPOSAL_SCHEMA = ROOT / "schemas/trusted_runtime/identity_update_proposal.schema.json"
PROJECTION_SCHEMA = (
    ROOT / "schemas/trusted_runtime/agent_personality_projection.schema.json"
)


def _aggregate(episodes):
    return aggregate_verified_episode_v02_mappings(
        episodes,
        scope=DEFAULT_SCOPE,
        repeat_key=DEFAULT_REPEAT_KEY,
        candidate_statement=DEFAULT_STATEMENT,
        created_at="2026-06-25T12:00:00Z",
    )


def test_three_verified_episodes_reach_active_personality_projection() -> None:
    result = run_identity_personality_acceptance()

    assert result.aggregation.status is AggregationStatus.READY_FOR_REVIEW
    assert result.aggregation.support_count == 3
    assert result.aggregation.failure_count == 0
    assert result.aggregation.contradiction_count == 0
    assert result.proposal.applied is False
    assert result.proposal.approval_required is True
    assert result.approval.proposer_actor != result.approval.approver_actor
    assert result.application.previous_version == 1
    assert result.application.new_version == 2
    assert result.active_profile.version == 2
    assert result.active_profile.source_application_ref == result.application.application_id

    assert len(result.projection.working_tendencies) == 1
    item = result.projection.working_tendencies[0]
    assert item.key == "test_before_claim"
    assert item.value is True
    assert item.metadata["identity_trait_key"] == DEFAULT_TRAIT_KEY
    assert result.aggregation.aggregation_id in item.source_refs
    assert result.proposal.proposal_id in item.source_refs
    assert result.approval.approval_id in item.source_refs
    for episode_ref in result.aggregation.supporting_episode_refs:
        assert episode_ref in item.source_refs
    assert result.application.application_id in result.projection.source_refs
    assert result.active_profile.profile_ref in result.projection.source_refs
    assert result.projection_validation.validity is ProjectionValidity.ACTIVE

    payload = result.to_dict()
    assert all(value is False for value in payload["authority_effects"].values())
    assert all(
        value is False
        for value in payload["projection"]["authority_effects"].values()
    )
    assert "Execution authorization: **false**" in result.runtime_markdown
    assert "Tool access grant or denial: **false**" in result.runtime_markdown
    assert "Identity approval or application: **false**" in result.runtime_markdown


def test_aggregation_proposal_and_projection_match_canonical_schemas() -> None:
    result = run_identity_personality_acceptance()

    cases = (
        (AGGREGATION_SCHEMA, result.aggregation.to_dict()),
        (PROPOSAL_SCHEMA, result.proposal.to_dict()),
        (PROJECTION_SCHEMA, result.projection.to_dict()),
    )
    for schema_path, payload in cases:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert list(Draft202012Validator(schema).iter_errors(payload)) == []


def test_one_or_two_episodes_cannot_create_identity_proposal() -> None:
    one = _aggregate((build_verified_episode_v02(index=1),))
    two = _aggregate(
        (
            build_verified_episode_v02(index=1),
            build_verified_episode_v02(index=2),
        )
    )

    assert one.status is AggregationStatus.INSUFFICIENT_SUPPORT
    assert two.status is AggregationStatus.INSUFFICIENT_SUPPORT
    assert one.proposal is None
    assert two.proposal is None


def test_contradicting_episode_blocks_identity_and_personality_path() -> None:
    contradiction = build_verified_episode_v02(
        index=4,
        outcome_class="unexpected",
        evidence_role="contradicting",
        statement="The review claimed success before the verification completed.",
        confidence=0.96,
    )
    aggregation = _aggregate(
        (
            build_verified_episode_v02(index=1),
            build_verified_episode_v02(index=2),
            build_verified_episode_v02(index=3),
            contradiction,
        )
    )

    assert aggregation.status is AggregationStatus.CONFLICTED
    assert aggregation.support_count == 3
    assert aggregation.contradiction_count == 1
    assert aggregation.proposal is None
    assert contradiction["episode_id"] in aggregation.contradicting_episode_refs


def test_replay_is_deterministic_and_cannot_reapply_identity() -> None:
    first = run_identity_personality_acceptance()
    second = run_identity_personality_acceptance()

    assert first.acceptance_id == second.acceptance_id
    assert first.aggregation.aggregation_id == second.aggregation.aggregation_id
    assert first.proposal.proposal_id == second.proposal.proposal_id
    assert first.approval.approval_id == second.approval.approval_id
    assert first.patch.patch_id == second.patch.patch_id
    assert first.patch_commit.commit_id == second.patch_commit.commit_id
    assert first.application.application_id == second.application.application_id
    assert first.active_profile.profile_ref == second.active_profile.profile_ref
    assert first.projection.projection_id == second.projection.projection_id

    with pytest.raises(IdentityAlreadyAppliedError, match="must not reapply"):
        activate_identity_profile_patch(
            first.proposal,
            first.approval,
            first.patch,
            first.patch_commit,
            first.base_profile,
            activated_at="2026-06-25T12:04:00Z",
            activated_by="runtime:profile-controller",
            existing_application_refs=(first.application.application_id,),
        )


def test_rollback_makes_old_personality_projection_stale() -> None:
    result = run_identity_personality_acceptance()
    rollback_profile, rollback = rollback_identity_application(
        result.active_profile,
        result.base_profile,
        result.application,
        reason="Acceptance rollback proves projection invalidation.",
        rolled_back_at="2026-06-25T12:10:00Z",
        rolled_back_by="human:identity-owner",
    )
    validation = validate_personality_projection(
        result.projection,
        active_profile=rollback_profile,
        evaluated_at="2026-06-25T12:11:00Z",
    )

    assert rollback.rollback_profile_ref == rollback_profile.profile_ref
    assert rollback_profile.version == 3
    assert DEFAULT_TRAIT_KEY not in rollback_profile.traits
    assert validation.validity is ProjectionValidity.STALE
    assert "IDENTITY_PROFILE_SUPERSEDED_OR_ROLLED_BACK" in validation.reason_codes
    assert validation.to_dict()["projection_mutation_allowed"] is False
    assert validation.to_dict()["identity_mutation_allowed"] is False
    assert validation.to_dict()["execution_authorized"] is False
