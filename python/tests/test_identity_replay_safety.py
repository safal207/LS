from __future__ import annotations

import pytest

from trusted_runtime.identity_governance import (
    ApprovalDecision,
    IdentityAlreadyAppliedError,
    IdentityPatchChange,
    IdentityProfile,
    PatchOperation,
    activate_identity_profile_patch,
    commit_identity_profile_patch,
    create_identity_profile_patch,
    decide_identity_update_proposal,
)
from trusted_runtime.identity_learning import ApprovalState, IdentityUpdateProposal


def test_replay_does_not_reapply_identity_patch() -> None:
    proposal = IdentityUpdateProposal(
        proposal_id="proposal:1", scope="review", repeat_key="key:1",
        candidate_statement="Use bounded evidence.",
        created_at="2026-06-24T01:00:00Z", aggregated_confidence=0.8,
        support_count=3, required_support_count=3,
        supporting_episode_refs=("e:1", "e:2", "e:3"), evidence_refs=("x:1",),
        approval_required=True, approval_state=ApprovalState.PENDING,
        applied=False, application_ref=None,
    )
    profile = IdentityProfile(
        profile_id="agent:v1", agent_id="agent:1", version=1,
        traits={"bounded": False}, created_at="2026-06-24T00:00:00Z",
        previous_profile_ref=None, source_application_ref=None,
    )
    approval = decide_identity_update_proposal(
        proposal, proposer_actor="agent:1", approver_actor="human:1",
        decision=ApprovalDecision.APPROVE, reason="Approved independently.",
        decided_at="2026-06-24T02:00:00Z", expires_at="2026-06-24T03:00:00Z",
    )
    patch = create_identity_profile_patch(
        proposal, approval, profile,
        changes=(IdentityPatchChange(PatchOperation.SET, "bounded", True),),
        created_at="2026-06-24T02:10:00Z", created_by="runtime:1",
        now="2026-06-24T02:10:00Z",
    )
    commit = commit_identity_profile_patch(
        patch, committed_at="2026-06-24T02:15:00Z",
        committed_by="runtime:journal", durable_ref="journal:1",
    )
    _, application = activate_identity_profile_patch(
        proposal, approval, patch, commit, profile,
        activated_at="2026-06-24T02:20:00Z", activated_by="runtime:controller",
    )
    with pytest.raises(IdentityAlreadyAppliedError, match="must not reapply"):
        activate_identity_profile_patch(
            proposal, approval, patch, commit, profile,
            activated_at="2026-06-24T02:20:00Z",
            activated_by="runtime:controller",
            existing_application_refs=(application.application_id,),
        )
