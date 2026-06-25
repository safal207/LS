#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from modules.trusted_runtime.continuity_coordinator import KnowledgeClass  # noqa: E402
from modules.trusted_runtime.roles_permissions_track_center import (  # noqa: E402
    ROLES_PERMISSIONS_TRACK,
    AuthorityBasis,
    AuthorityStatus,
    RolePermissionEvent,
    RolePermissionEventType,
    process_role_permission_event,
)


def make(
    event_id: str,
    status: AuthorityStatus,
    basis: AuthorityBasis,
    *,
    event_type: RolePermissionEventType = RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
    contexts: tuple[str, ...] = ("context:production",),
    approvals: tuple[str, ...] = (),
    candidate: bool = False,
) -> RolePermissionEvent:
    repeated = candidate
    return RolePermissionEvent(
        event_id=event_id,
        authority_id="authority:deploy",
        subject_id="agent:release-bot",
        event_type=event_type,
        authority_status=status,
        authority_basis=basis,
        action="deploy",
        resource="service:payments",
        scope_ref="scope:production",
        knowledge_class=KnowledgeClass.FACT,
        statement="Bounded role and permission observation.",
        occurred_at="2026-06-25T11:30:00Z",
        confidence=0.94,
        repeat_count=2 if repeated else 1,
        evidence_refs=("evidence:1", "evidence:2") if repeated else ("evidence:1",),
        provenance_refs=("provenance:1", "provenance:2") if repeated else ("provenance:1",),
        context_refs=contexts,
        observer_refs=("observer:security", "observer:release") if repeated else ("observer:security",),
        role_refs=("role:release-operator",),
        approval_refs=approvals,
        identity_candidate_statement=(
            "Escalate when authority scope is incomplete." if candidate else None
        ),
        identity_scope=ROLES_PERMISSIONS_TRACK if candidate else None,
        identity_repeat_key="authority:escalate-incomplete" if candidate else None,
    )


def main() -> int:
    output = ROOT / "build/roles-permissions-track-center"
    output.mkdir(parents=True, exist_ok=True)
    events = (
        make("authority-event:role-only", AuthorityStatus.ACTIVE, AuthorityBasis.ROLE_ASSIGNMENT),
        make("authority-event:pending", AuthorityStatus.PENDING_APPROVAL, AuthorityBasis.APPROVAL),
        make("authority-event:revoked", AuthorityStatus.REVOKED, AuthorityBasis.DIRECT_PERMISSION),
        make("authority-event:valid", AuthorityStatus.ACTIVE, AuthorityBasis.DIRECT_PERMISSION),
        make(
            "authority-event:pattern",
            AuthorityStatus.PENDING_APPROVAL,
            AuthorityBasis.APPROVAL,
            event_type=RolePermissionEventType.ESCALATION_PATTERN_VERIFIED,
            contexts=("context:staging", "context:production"),
            candidate=True,
        ),
    )
    results = [
        process_role_permission_event(item, processed_at="2026-06-25T11:31:00Z")
        for item in events
    ]
    summary = {
        "schema_version": "trusted_runtime.roles_permissions_demo.v0.1",
        "result": "PASS",
        "decisions": [
            {
                "event_id": result.event.event_id,
                "decision": result.assessment.decision.value,
                "lesson": result.assessment.lesson_candidate is not None,
                "access_grant_allowed": False,
                "approval_allowed": False,
                "stable_identity_update_allowed": False,
                "execution_authorized": False,
            }
            for result in results
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
