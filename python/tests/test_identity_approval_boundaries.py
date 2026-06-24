from __future__ import annotations

from dataclasses import replace
from typing import Optional

import pytest

from trusted_runtime.identity_governance import (
    ApprovalDecision,
    IdentityGovernanceError,
    IdentityPatchChange,
    IdentityProfile,
    PatchOperation,
    create_identity_profile_patch,
    decide_identity_update_proposal,
    invalidate_identity_approval,
)
from trusted_runtime.identity_learning import ApprovalState, IdentityUpdateProposal


def proposal() -> IdentityUpdateProposal:
    return IdentityUpdateProposal(
        proposal_id="identity-proposal:1",
        scope="trusted-pr-review-mvp",
        repeat_key="reviewer:bounded-evidence-preference",
        candidate_statement="Prefer bounded evidence before protected actions.",
        created_at="2026-06-24T01:00:00Z",
        aggregated_confidence=0.8,
        support_count=3,
        required_support_count=3,
        supporting_episode_refs=("episode:1", "episode:2", "episode:3"),
        evidence_refs=("evidence:1", "evidence:2", "evidence:3"),
        approval_required=True,
        approval_state=ApprovalState.PENDING,
        applied=False,
        application_ref=None,
    )


def profile() -> IdentityProfile:
    return IdentityProfile(
        profile_id="agent:reviewer:v1",
        agent_id="agent:reviewer",
        version=1,
        traits={"requires_bounded_evidence": False},
        created_at="2026-06-24T00:00:00Z",
        previous_profile_ref=None,
        source_application_ref=None,
    )


def approval(item: Optional[IdentityUpdateProposal] = None):
    return decide_identity_update_proposal(
        item or proposal(),
        proposer_actor="agent:reviewer",
        approver_actor="human:owner",
        decision=ApprovalDecision.APPROVE,
        reason="Repeated verified evidence supports a bounded update.",
        decided_at="2026-06-24T02:00:00Z",
        expires_at="2026-06-24T03:00:00Z",
    )


def one_change():
    return (
        IdentityPatchChange(
            operation=PatchOperation.SET,
            key="requires_bounded_evidence",
            value=True,
        ),
    )


def test_self_approval_is_prohibited() -> None:
    with pytest.raises(ValueError, match="self-approval is prohibited"):
        decide_identity_update_proposal(
            proposal(),
            proposer_actor="agent:reviewer",
            approver_actor="agent:reviewer",
            decision=ApprovalDecision.APPROVE,
            reason="Self approval must fail.",
            decided_at="2026-06-24T02:00:00Z",
            expires_at="2026-06-24T03:00:00Z",
        )


@pytest.mark.parametrize("decision", (ApprovalDecision.REJECT, ApprovalDecision.EXPIRE))
def test_non_approved_decision_cannot_create_patch(decision) -> None:
    item = proposal()
    record = decide_identity_update_proposal(
        item,
        proposer_actor="agent:reviewer",
        approver_actor="human:owner",
        decision=decision,
        reason="No activation permitted.",
        decided_at="2026-06-24T02:00:00Z",
    )
    with pytest.raises(IdentityGovernanceError, match="requires APPROVE"):
        create_identity_profile_patch(
            item,
            record,
            profile(),
            changes=one_change(),
            created_at="2026-06-24T02:10:00Z",
            created_by="runtime:identity-governance",
            now="2026-06-24T02:10:00Z",
        )


def test_approval_is_bound_to_exact_proposal_digest() -> None:
    original = proposal()
    changed = replace(original, candidate_statement="Different identity hypothesis.")
    with pytest.raises(IdentityGovernanceError, match="exact proposal"):
        create_identity_profile_patch(
            changed,
            approval(original),
            profile(),
            changes=one_change(),
            created_at="2026-06-24T02:10:00Z",
            created_by="runtime:identity-governance",
            now="2026-06-24T02:10:00Z",
        )


def test_new_contradiction_invalidates_approval() -> None:
    item = proposal()
    approved = approval(item)
    invalidated = invalidate_identity_approval(
        item,
        approved,
        contradiction_refs=("episode:contradiction:4",),
        invalidated_at="2026-06-24T02:20:00Z",
        invalidated_by="human:risk-owner",
        reason="New verified evidence contradicts the proposal.",
    )
    assert invalidated.decision is ApprovalDecision.INVALIDATE
    assert invalidated.expires_at is None
    assert invalidated.metadata["invalidates_approval_ref"] == approved.approval_id
    with pytest.raises(IdentityGovernanceError, match="requires APPROVE"):
        create_identity_profile_patch(
            item,
            invalidated,
            profile(),
            changes=one_change(),
            created_at="2026-06-24T02:25:00Z",
            created_by="runtime:identity-governance",
            now="2026-06-24T02:25:00Z",
        )


def test_expired_approval_window_cannot_create_patch() -> None:
    item = proposal()
    with pytest.raises(IdentityGovernanceError, match="has expired"):
        create_identity_profile_patch(
            item,
            approval(item),
            profile(),
            changes=one_change(),
            created_at="2026-06-24T03:10:00Z",
            created_by="runtime:identity-governance",
            now="2026-06-24T03:10:00Z",
        )
