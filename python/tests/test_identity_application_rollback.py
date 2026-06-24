from __future__ import annotations

from trusted_runtime.identity_governance import (
    ApprovalDecision,
    IdentityPatchChange,
    IdentityProfile,
    PatchOperation,
    activate_identity_profile_patch,
    commit_identity_profile_patch,
    create_identity_profile_patch,
    decide_identity_update_proposal,
    rollback_identity_application,
)
from trusted_runtime.identity_learning import ApprovalState, IdentityUpdateProposal


def test_application_and_rollback_create_new_versions() -> None:
    proposal = IdentityUpdateProposal(
        proposal_id="proposal:1", scope="review", repeat_key="key:1",
        candidate_statement="Use bounded evidence.",
        created_at="2026-06-24T01:00:00Z", aggregated_confidence=0.8,
        support_count=3, required_support_count=3,
        supporting_episode_refs=("e:1", "e:2", "e:3"),
        evidence_refs=("x:1",), approval_required=True,
        approval_state=ApprovalState.PENDING, applied=False, application_ref=None,
    )
    base = IdentityProfile(
        profile_id="agent:v1", agent_id="agent:1", version=1,
        traits={"bounded": False}, created_at="2026-06-24T00:00:00Z",
        previous_profile_ref=None, source_application_ref=None,
    )
    approval = decide_identity_update_proposal(
        proposal, proposer_actor="agent:1", approver_actor="human:1",
        decision=ApprovalDecision.APPROVE, reason="Approved independently.",
        decided_at="2026-06-24T02:00:00Z",
        expires_at="2026-06-24T03:00:00Z",
    )
    patch = create_identity_profile_patch(
        proposal, approval, base,
        changes=(IdentityPatchChange(PatchOperation.SET, "bounded", True),),
        created_at="2026-06-24T02:10:00Z", created_by="runtime:1",
        now="2026-06-24T02:10:00Z",
    )
    commit = commit_identity_profile_patch(
        patch, committed_at="2026-06-24T02:15:00Z",
        committed_by="runtime:journal", durable_ref="journal:1",
    )
    updated, application = activate_identity_profile_patch(
        proposal, approval, patch, commit, base,
        activated_at="2026-06-24T02:20:00Z",
        activated_by="runtime:controller",
    )
    assert updated.version == 2
    assert updated.previous_profile_ref == base.profile_ref
    assert updated.traits["bounded"] is True
    assert application.new_profile_ref == updated.profile_ref

    restored, rollback = rollback_identity_application(
        updated, base, application, reason="Revert after review.",
        rolled_back_at="2026-06-24T04:00:00Z", rolled_back_by="human:1",
    )
    assert restored.version == 3
    assert restored.previous_profile_ref == updated.profile_ref
    assert restored.traits == base.traits
    assert rollback.rollback_profile_ref == restored.profile_ref
    assert rollback.metadata["history_deleted"] is False
