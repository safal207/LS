from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
from trusted_runtime.identity_timeline import (
    persist_identity_lifecycle,
    replay_identity_timeline,
)
from trusted_runtime.persistence import JsonlEventStoreAdapter


def build_timeline_bundle(data_root: Path, agent_id: str) -> dict[str, Any]:
    bundle = data_root / _slug(agent_id)
    bundle.mkdir(parents=True, exist_ok=True)

    proposal = IdentityUpdateProposal(
        proposal_id=f"identity-proposal:{agent_id}",
        scope="trusted-pr-review-mvp",
        repeat_key=f"{agent_id}:bounded-evidence",
        candidate_statement="Prefer bounded evidence before protected actions.",
        created_at="2026-06-24T01:00:00Z",
        aggregated_confidence=0.8,
        support_count=3,
        required_support_count=3,
        supporting_episode_refs=(
            f"episode:{agent_id}:1",
            f"episode:{agent_id}:2",
            f"episode:{agent_id}:3",
        ),
        evidence_refs=(f"evidence:{agent_id}:1",),
        approval_required=True,
        approval_state=ApprovalState.PENDING,
        applied=False,
        application_ref=None,
    )
    profile_v1 = IdentityProfile(
        profile_id=f"{agent_id}:v1",
        agent_id=agent_id,
        version=1,
        traits={"requires_bounded_evidence": False, "review_style": "balanced"},
        created_at="2026-06-24T00:00:00Z",
        previous_profile_ref=None,
        source_application_ref=None,
    )
    approval = decide_identity_update_proposal(
        proposal,
        proposer_actor=agent_id,
        approver_actor="human:identity-owner",
        decision=ApprovalDecision.APPROVE,
        reason="Independent approval for a bounded reversible update.",
        decided_at="2026-06-24T02:00:00Z",
        expires_at="2026-06-24T03:00:00Z",
    )
    patch = create_identity_profile_patch(
        proposal,
        approval,
        profile_v1,
        changes=(
            IdentityPatchChange(
                operation=PatchOperation.SET,
                key="requires_bounded_evidence",
                value=True,
            ),
            IdentityPatchChange(
                operation=PatchOperation.SET,
                key="bounded_evidence_confidence",
                value=0.8,
            ),
        ),
        created_at="2026-06-24T02:10:00Z",
        created_by="runtime:identity-governance",
        now="2026-06-24T02:10:00Z",
    )
    commit = commit_identity_profile_patch(
        patch,
        committed_at="2026-06-24T02:15:00Z",
        committed_by="runtime:identity-journal",
        durable_ref=f"journal:{agent_id}:1",
    )
    profile_v2, application = activate_identity_profile_patch(
        proposal,
        approval,
        patch,
        commit,
        profile_v1,
        activated_at="2026-06-24T02:20:00Z",
        activated_by="runtime:profile-controller",
    )
    profile_v3, rollback = rollback_identity_application(
        profile_v2,
        profile_v1,
        application,
        reason="Fixture rollback preserves the full identity history.",
        rolled_back_at="2026-06-24T04:00:00Z",
        rolled_back_by="human:identity-owner",
    )

    events_path = bundle / "identity-events.jsonl"
    store = JsonlEventStoreAdapter(events_path)
    persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=profile_v1.to_dict(),
        proposal=proposal.to_dict(),
        approval=approval.to_dict(),
        patch=patch.to_dict(),
        commit=commit.to_dict(),
        application=application.to_dict(),
        profile_v2=profile_v2.to_dict(),
        rollback=rollback.to_dict(),
        profile_v3=profile_v3.to_dict(),
    )
    timeline = replay_identity_timeline(store, agent_id=agent_id).to_dict()
    timeline_path = bundle / "identity-timeline.json"
    timeline_path.write_text(
        json.dumps(timeline, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "agent_id": agent_id,
        "bundle": bundle,
        "events_path": events_path,
        "timeline_path": timeline_path,
        "timeline": timeline,
    }


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value)
