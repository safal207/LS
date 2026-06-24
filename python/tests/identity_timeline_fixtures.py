from __future__ import annotations

from typing import Any

from trusted_runtime.persistence import digest_json


def profile_ref(profile: dict[str, Any]) -> str:
    return "identity-profile:sha256:" + digest_json(profile)


def lifecycle_records() -> dict[str, dict[str, Any]]:
    agent_id = "agent:timeline-test"
    profile_v1 = {
        "schema_version": "trusted_runtime.identity_profile.v0.1",
        "profile_id": f"{agent_id}:v1",
        "agent_id": agent_id,
        "version": 1,
        "traits": {"bounded": False, "style": "balanced"},
        "created_at": "2026-06-24T00:00:00Z",
        "previous_profile_ref": None,
        "source_application_ref": None,
        "active": True,
        "metadata": {},
    }
    proposal = {
        "schema_version": "trusted_runtime.identity_update_proposal.v0.1",
        "proposal_id": "identity-proposal:test:1",
        "scope": "trusted-pr-review-mvp",
        "repeat_key": "reviewer:bounded-evidence",
        "candidate_statement": "Prefer bounded evidence.",
        "created_at": "2026-06-24T01:00:00Z",
        "aggregated_confidence": 0.8,
        "support_count": 3,
        "required_support_count": 3,
        "supporting_episode_refs": ["episode:1", "episode:2", "episode:3"],
        "evidence_refs": ["evidence:1", "evidence:2", "evidence:3"],
        "approval_required": True,
        "approval_state": "PENDING",
        "applied": False,
        "application_ref": None,
        "policy_version": "identity_update.proposal.v0.1",
        "metadata": {},
    }
    approval = {
        "schema_version": "trusted_runtime.identity_update_approval.v0.1",
        "approval_id": "identity-approval:test:1",
        "proposal_id": proposal["proposal_id"],
        "proposal_digest": digest_json(proposal),
        "proposer_actor": agent_id,
        "approver_actor": "human:identity-owner",
        "decision": "APPROVE",
        "reason": "Independent approval.",
        "decided_at": "2026-06-24T02:00:00Z",
        "expires_at": "2026-06-24T03:00:00Z",
        "contradiction_refs": [],
        "policy_version": "identity_governance.v0.1",
        "metadata": {},
    }
    patch = {
        "schema_version": "trusted_runtime.identity_profile_patch.v0.1",
        "patch_id": "identity-patch:test:1",
        "proposal_id": proposal["proposal_id"],
        "proposal_digest": digest_json(proposal),
        "approval_id": approval["approval_id"],
        "agent_id": agent_id,
        "base_profile_ref": profile_ref(profile_v1),
        "base_profile_version": 1,
        "changes": [
            {"operation": "SET", "key": "bounded", "value": True},
            {"operation": "SET", "key": "confidence", "value": 0.8},
        ],
        "created_at": "2026-06-24T02:10:00Z",
        "created_by": "runtime:identity-governance",
        "metadata": {},
    }
    commit = {
        "schema_version": "trusted_runtime.identity_patch_commit.v0.1",
        "commit_id": "identity-patch-commit:test:1",
        "patch_id": patch["patch_id"],
        "patch_digest": digest_json(patch),
        "committed_at": "2026-06-24T02:15:00Z",
        "committed_by": "runtime:identity-journal",
        "durable_ref": "journal:test:1",
        "metadata": {"commit_before_activation": True},
    }
    application_id = "identity-application:test:1"
    profile_v2 = {
        "schema_version": "trusted_runtime.identity_profile.v0.1",
        "profile_id": f"{agent_id}:v2",
        "agent_id": agent_id,
        "version": 2,
        "traits": {"bounded": True, "style": "balanced", "confidence": 0.8},
        "created_at": "2026-06-24T02:20:00Z",
        "previous_profile_ref": profile_ref(profile_v1),
        "source_application_ref": application_id,
        "active": True,
        "metadata": {},
    }
    application = {
        "schema_version": "trusted_runtime.identity_application.v0.1",
        "application_id": application_id,
        "proposal_id": proposal["proposal_id"],
        "approval_id": approval["approval_id"],
        "patch_id": patch["patch_id"],
        "patch_digest": digest_json(patch),
        "commit_id": commit["commit_id"],
        "agent_id": agent_id,
        "previous_profile_ref": profile_ref(profile_v1),
        "new_profile_ref": profile_ref(profile_v2),
        "previous_version": 1,
        "new_version": 2,
        "activated_at": "2026-06-24T02:20:00Z",
        "activated_by": "runtime:profile-controller",
        "replay_safe": True,
        "metadata": {"activation_after_commit": True},
    }
    rollback_id = "identity-rollback:test:1"
    profile_v3 = {
        "schema_version": "trusted_runtime.identity_profile.v0.1",
        "profile_id": f"{agent_id}:v3",
        "agent_id": agent_id,
        "version": 3,
        "traits": dict(profile_v1["traits"]),
        "created_at": "2026-06-24T04:00:00Z",
        "previous_profile_ref": profile_ref(profile_v2),
        "source_application_ref": rollback_id,
        "active": True,
        "metadata": {"rollback_of_application": application_id},
    }
    rollback = {
        "schema_version": "trusted_runtime.identity_rollback.v0.1",
        "rollback_id": rollback_id,
        "agent_id": agent_id,
        "application_id": application_id,
        "from_profile_ref": profile_ref(profile_v2),
        "restored_from_profile_ref": profile_ref(profile_v1),
        "rollback_profile_ref": profile_ref(profile_v3),
        "from_version": 2,
        "rollback_version": 3,
        "reason": "Restore prior profile.",
        "rolled_back_at": "2026-06-24T04:00:00Z",
        "rolled_back_by": "human:identity-owner",
        "metadata": {"history_deleted": False},
    }
    return {
        "agent_id": {"value": agent_id},
        "profile_v1": profile_v1,
        "proposal": proposal,
        "approval": approval,
        "patch": patch,
        "commit": commit,
        "application": application,
        "profile_v2": profile_v2,
        "rollback": rollback,
        "profile_v3": profile_v3,
    }
