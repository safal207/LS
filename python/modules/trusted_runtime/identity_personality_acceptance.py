"""Deterministic acceptance path from verified experience to runtime personality.

This focused path complements the broader Identity Control Plane acceptance. It
proves that VerifiedEpisode v0.2 evidence can produce a review-only proposal,
pass independent governance, activate exactly one profile version, and become a
read-only AgentPersonalityProjection without acquiring runtime authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .agent_personality_projection import (
    AgentPersonalityProjection,
    PersonalityProjectionValidation,
    ProjectionScope,
    ProjectionScopeLevel,
    project_agent_personality,
    render_personality_projection_markdown,
    validate_personality_projection,
)
from .identity_governance import (
    ApprovalDecision,
    IdentityApplicationRecord,
    IdentityPatchChange,
    IdentityPatchCommit,
    IdentityProfile,
    IdentityProfilePatch,
    IdentityUpdateApproval,
    PatchOperation,
    activate_identity_profile_patch,
    commit_identity_profile_patch,
    create_identity_profile_patch,
    decide_identity_update_proposal,
)
from .identity_learning import IdentityUpdateProposal
from .identity_learning_v02 import (
    LessonAggregationV02,
    aggregate_verified_episode_v02_mappings,
)


IDENTITY_PERSONALITY_ACCEPTANCE_VERSION = (
    "trusted_runtime.identity_personality_acceptance.v0.1"
)
IDENTITY_PERSONALITY_ACCEPTANCE_POLICY_VERSION = (
    "identity_personality_acceptance.v0.1"
)
DEFAULT_AGENT_ID = "agent:identity-personality-acceptance"
DEFAULT_SCOPE = "project:ls"
DEFAULT_REPEAT_KEY = "working-tendency:test-before-claim"
DEFAULT_STATEMENT = "Repeated verified reviews support testing before claiming success."
DEFAULT_TRAIT_KEY = "working_tendencies.test_before_claim"


@dataclass(frozen=True)
class IdentityPersonalityAcceptanceResult:
    acceptance_id: str
    agent_id: str
    episode_payloads: tuple[Mapping[str, Any], ...]
    aggregation: LessonAggregationV02
    proposal: IdentityUpdateProposal
    approval: IdentityUpdateApproval
    patch: IdentityProfilePatch
    patch_commit: IdentityPatchCommit
    base_profile: IdentityProfile
    active_profile: IdentityProfile
    application: IdentityApplicationRecord
    projection: AgentPersonalityProjection
    projection_validation: PersonalityProjectionValidation
    runtime_markdown: str
    policy_version: str = IDENTITY_PERSONALITY_ACCEPTANCE_POLICY_VERSION
    schema_version: str = IDENTITY_PERSONALITY_ACCEPTANCE_VERSION

    def __post_init__(self) -> None:
        required = (
            self.acceptance_id,
            self.agent_id,
            self.runtime_markdown,
            self.policy_version,
        )
        if not all(required):
            raise ValueError("identity-personality acceptance fields must not be empty")
        if self.schema_version != IDENTITY_PERSONALITY_ACCEPTANCE_VERSION:
            raise ValueError(
                f"unsupported identity-personality acceptance: {self.schema_version}"
            )
        if len(self.episode_payloads) != 3:
            raise ValueError("acceptance path requires exactly three source episodes")
        if self.aggregation.proposal is None:
            raise ValueError("acceptance aggregation must contain a proposal")
        if self.proposal.proposal_id != self.aggregation.proposal.proposal_id:
            raise ValueError("acceptance proposal must come from the aggregation")
        if self.approval.proposal_id != self.proposal.proposal_id:
            raise ValueError("acceptance approval must bind the proposal")
        if self.patch.approval_id != self.approval.approval_id:
            raise ValueError("acceptance patch must bind the approval")
        if self.patch_commit.patch_id != self.patch.patch_id:
            raise ValueError("acceptance commit must bind the patch")
        if self.application.patch_id != self.patch.patch_id:
            raise ValueError("acceptance application must bind the patch")
        if self.active_profile.source_application_ref != self.application.application_id:
            raise ValueError("active profile must bind the identity application")
        if self.projection.identity_profile_ref != self.active_profile.profile_ref:
            raise ValueError("projection must bind the active profile")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "acceptance_id": self.acceptance_id,
            "agent_id": self.agent_id,
            "episode_payloads": [dict(payload) for payload in self.episode_payloads],
            "aggregation": self.aggregation.to_dict(),
            "proposal": self.proposal.to_dict(),
            "approval": self.approval.to_dict(),
            "patch": self.patch.to_dict(),
            "patch_commit": self.patch_commit.to_dict(),
            "base_profile": self.base_profile.to_dict(),
            "active_profile": self.active_profile.to_dict(),
            "application": self.application.to_dict(),
            "projection": self.projection.to_dict(),
            "projection_validation": self.projection_validation.to_dict(),
            "runtime_markdown": self.runtime_markdown,
            "authority_effects": {
                "may_auto_approve_identity": False,
                "may_reapply_identity_on_replay": False,
                "may_authorize_execution": False,
                "may_grant_tool_access": False,
                "may_deny_tool_access": False,
                "may_bypass_governance": False,
                "may_expand_scope": False,
            },
            "policy_version": self.policy_version,
        }


def run_identity_personality_acceptance(
    *,
    agent_id: str = DEFAULT_AGENT_ID,
    scope: str = DEFAULT_SCOPE,
    repeat_key: str = DEFAULT_REPEAT_KEY,
    statement: str = DEFAULT_STATEMENT,
    created_at: str = "2026-06-25T12:00:00Z",
) -> IdentityPersonalityAcceptanceResult:
    """Run the governed experience-to-personality path in memory.

    The function has no external side effects. It returns immutable artifacts
    that a caller may persist separately for review.
    """

    episodes = tuple(
        build_verified_episode_v02(
            index=index,
            agent_id=agent_id,
            scope=scope,
            repeat_key=repeat_key,
            statement=statement,
            confidence=confidence,
        )
        for index, confidence in ((1, 0.82), (2, 0.88), (3, 0.94))
    )
    aggregation = aggregate_verified_episode_v02_mappings(
        episodes,
        scope=scope,
        repeat_key=repeat_key,
        candidate_statement=statement,
        created_at=created_at,
        required_support_count=3,
        metadata={
            "acceptance_path": IDENTITY_PERSONALITY_ACCEPTANCE_POLICY_VERSION,
            "agent_id": agent_id,
        },
    )
    proposal = aggregation.proposal
    if proposal is None:
        raise RuntimeError("three supporting v0.2 episodes did not create a proposal")

    base_profile = IdentityProfile(
        profile_id=f"{agent_id}:v1",
        agent_id=agent_id,
        version=1,
        traits={},
        created_at="2026-06-25T11:50:00Z",
        previous_profile_ref=None,
        source_application_ref=None,
        active=True,
        metadata={"acceptance_baseline": True},
    )
    approval = decide_identity_update_proposal(
        proposal,
        proposer_actor=f"runtime:{agent_id}",
        approver_actor="human:identity-owner",
        decision=ApprovalDecision.APPROVE,
        reason="Independent approval for the focused identity-personality acceptance.",
        decided_at="2026-06-25T12:01:00Z",
        expires_at="2026-06-25T13:00:00Z",
        metadata={
            "acceptance_path": IDENTITY_PERSONALITY_ACCEPTANCE_POLICY_VERSION,
            "source_aggregation_ref": aggregation.aggregation_id,
        },
    )
    trait_value = {
        "value": True,
        "state": "ACTIVE",
        "confidence": aggregation.aggregated_confidence,
        "source_refs": [
            aggregation.aggregation_id,
            proposal.proposal_id,
            approval.approval_id,
            *aggregation.supporting_episode_refs,
        ],
        "scope": {"level": "individual"},
        "expires_at": None,
        "disputed": False,
        "conflict_refs": [],
    }
    patch = create_identity_profile_patch(
        proposal,
        approval,
        base_profile,
        changes=(
            IdentityPatchChange(
                operation=PatchOperation.SET,
                key=DEFAULT_TRAIT_KEY,
                value=trait_value,
            ),
        ),
        created_at="2026-06-25T12:02:00Z",
        created_by="runtime:identity-governance",
        now="2026-06-25T12:02:00Z",
        metadata={
            "acceptance_path": IDENTITY_PERSONALITY_ACCEPTANCE_POLICY_VERSION,
            "source_aggregation_ref": aggregation.aggregation_id,
        },
    )
    patch_commit = commit_identity_profile_patch(
        patch,
        committed_at="2026-06-25T12:03:00Z",
        committed_by="runtime:identity-journal",
        durable_ref="identity-personality-acceptance:journal:1",
    )
    active_profile, application = activate_identity_profile_patch(
        proposal,
        approval,
        patch,
        patch_commit,
        base_profile,
        activated_at="2026-06-25T12:04:00Z",
        activated_by="runtime:profile-controller",
    )
    projection_scope = ProjectionScope(
        ProjectionScopeLevel.PROJECT,
        project_ref=scope,
    )
    projection = project_agent_personality(
        active_profile,
        scope=projection_scope,
        created_at="2026-06-25T12:05:00Z",
        expires_at="2026-06-26T12:05:00Z",
    )
    validation = validate_personality_projection(
        projection,
        active_profile=active_profile,
        evaluated_at="2026-06-25T12:06:00Z",
    )
    markdown = render_personality_projection_markdown(projection)

    acceptance_payload = {
        "agent_id": agent_id,
        "episode_ids": [payload["episode_id"] for payload in episodes],
        "aggregation_id": aggregation.aggregation_id,
        "proposal_id": proposal.proposal_id,
        "approval_id": approval.approval_id,
        "patch_id": patch.patch_id,
        "commit_id": patch_commit.commit_id,
        "application_id": application.application_id,
        "profile_ref": active_profile.profile_ref,
        "projection_id": projection.projection_id,
        "policy_version": IDENTITY_PERSONALITY_ACCEPTANCE_POLICY_VERSION,
    }
    return IdentityPersonalityAcceptanceResult(
        acceptance_id="identity-personality-acceptance:sha256:"
        + _digest(acceptance_payload),
        agent_id=agent_id,
        episode_payloads=episodes,
        aggregation=aggregation,
        proposal=proposal,
        approval=approval,
        patch=patch,
        patch_commit=patch_commit,
        base_profile=base_profile,
        active_profile=active_profile,
        application=application,
        projection=projection,
        projection_validation=validation,
        runtime_markdown=markdown,
    )


def build_verified_episode_v02(
    *,
    index: int,
    agent_id: str = DEFAULT_AGENT_ID,
    scope: str = DEFAULT_SCOPE,
    repeat_key: str = DEFAULT_REPEAT_KEY,
    statement: str = DEFAULT_STATEMENT,
    confidence: float = 0.9,
    outcome_class: str = "expected",
    evidence_role: str = "supporting",
    expires_at: Optional[str] = "2026-12-25T00:00:00Z",
    supersedes_episode_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build a deterministic source-backed VerifiedEpisode v0.2 mapping."""

    expected_projection = outcome_class == "expected"
    reason_codes = {
        "expected": "EXPECTED_OUTCOME_VERIFIED",
        "failed": "FAILURE_OUTCOME_VERIFIED",
        "unexpected": "UNEXPECTED_OUTCOME_VERIFIED",
    }
    if outcome_class not in reason_codes:
        raise ValueError("unsupported acceptance outcome_class")
    return {
        "schema_version": "trusted_runtime.verified_episode.v0.2",
        "episode_id": f"episode:sha256:{index:064x}",
        "task_id": f"identity-personality-task:{index}",
        "trail_id": f"identity-personality-trail:{index}",
        "orientation_ref": f"orientation:{agent_id}:{index}",
        "transition_id": f"identity-personality-transition:{index}",
        "decision": "ALLOW",
        "created_at": f"2026-06-25T11:{index:02d}:00Z",
        "status": "VERIFIED",
        "outcome_class": outcome_class,
        "expected_state_digest": "sha256:expected-state:test-before-claim",
        "verified_state_digest": f"sha256:verified-state:{index}",
        "provenance": {
            "verification_version": "outcome-verification-v0.1",
            "verification_reason_code": reason_codes[outcome_class],
            "execution_id": f"identity-personality-exec:{index}",
            "action_id": f"identity-personality-action:{index}",
            "action_digest": f"sha256:identity-personality-action:{index}",
            "actor_id": agent_id,
            "target_id": scope,
            "side_effect_key": "review:test-before-claim",
            "receipt_id": f"identity-personality-receipt:{index}",
            "receipt_digest": f"sha256:identity-personality-receipt:{index}",
            "causal_trace_id": f"identity-personality-trace:{index}",
            "observer_evidence_digests": [
                f"sha256:identity-personality-observer:{index}"
            ],
            "source_event_ids": [f"identity-personality-source-event:{index}"],
        },
        "lesson": {
            "statement": statement,
            "scope": scope,
            "confidence": confidence,
            "repeat_key": repeat_key,
            "evidence_role": evidence_role,
            "evidence_refs": [f"sha256:identity-personality-evidence:{index}"],
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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


__all__ = [
    "DEFAULT_AGENT_ID",
    "DEFAULT_REPEAT_KEY",
    "DEFAULT_SCOPE",
    "DEFAULT_STATEMENT",
    "DEFAULT_TRAIT_KEY",
    "IdentityPersonalityAcceptanceResult",
    "build_verified_episode_v02",
    "run_identity_personality_acceptance",
]
