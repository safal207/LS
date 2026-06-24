#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_governance import (  # noqa: E402
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
from modules.trusted_runtime.identity_learning import (  # noqa: E402
    ApprovalState,
    IdentityUpdateProposal,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run governed approval, application, and rollback demo.",
    )
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-id", default="agent:trusted-reviewer")
    parser.add_argument("--proposer", default="agent:trusted-reviewer")
    parser.add_argument("--approver", default="human:identity-owner")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    proposal = _proposal(_read(args.proposal))
    root = args.output
    root.mkdir(parents=True, exist_ok=True)

    profile_v1 = IdentityProfile(
        profile_id=f"{args.agent_id}:v1",
        agent_id=args.agent_id,
        version=1,
        traits={"requires_bounded_evidence": False},
        created_at="2026-06-24T00:00:00Z",
        previous_profile_ref=None,
        source_application_ref=None,
    )
    approval = decide_identity_update_proposal(
        proposal,
        proposer_actor=args.proposer,
        approver_actor=args.approver,
        decision=ApprovalDecision.APPROVE,
        reason="Independent owner approved a bounded and reversible update.",
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
                value=proposal.aggregated_confidence,
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
        durable_ref="journal:identity-patches:demo-1",
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
        reason="Demonstrate reversible profile governance.",
        rolled_back_at="2026-06-24T04:00:00Z",
        rolled_back_by=args.approver,
    )

    files = {
        "identity-profile-v1.json": profile_v1.to_dict(),
        "identity-update-approval.json": approval.to_dict(),
        "identity-profile-patch.json": patch.to_dict(),
        "identity-patch-commit.json": commit.to_dict(),
        "identity-profile-v2.json": profile_v2.to_dict(),
        "identity-application.json": application.to_dict(),
        "identity-profile-v3-rollback.json": profile_v3.to_dict(),
        "identity-rollback.json": rollback.to_dict(),
    }
    for name, payload in files.items():
        _write(root / name, payload)

    summary = {
        "proposal_ref": proposal.proposal_id,
        "approval_ref": approval.approval_id,
        "approval_decision": approval.decision.value,
        "patch_ref": patch.patch_id,
        "patch_committed_before_activation": True,
        "application_ref": application.application_id,
        "previous_version": profile_v1.version,
        "active_version_after_application": profile_v2.version,
        "rollback_ref": rollback.rollback_id,
        "active_version_after_rollback": profile_v3.version,
        "history_deleted": False,
        "self_approval": False,
        "replay_reapplies_patch": False,
    }
    _write(root / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


def _proposal(payload: Mapping[str, Any]) -> IdentityUpdateProposal:
    return IdentityUpdateProposal(
        proposal_id=str(payload["proposal_id"]),
        scope=str(payload["scope"]),
        repeat_key=str(payload["repeat_key"]),
        candidate_statement=str(payload["candidate_statement"]),
        created_at=str(payload["created_at"]),
        aggregated_confidence=float(payload["aggregated_confidence"]),
        support_count=int(payload["support_count"]),
        required_support_count=int(payload["required_support_count"]),
        supporting_episode_refs=tuple(payload["supporting_episode_refs"]),
        evidence_refs=tuple(payload["evidence_refs"]),
        approval_required=bool(payload["approval_required"]),
        approval_state=ApprovalState(str(payload["approval_state"])),
        applied=bool(payload["applied"]),
        application_ref=payload["application_ref"],
        policy_version=str(payload["policy_version"]),
        metadata=dict(payload["metadata"]),
        schema_version=str(payload["schema_version"]),
    )


def _read(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
