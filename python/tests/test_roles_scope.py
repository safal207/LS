from dataclasses import replace

import pytest

from trusted_runtime.continuity_coordinator import ContinuityDecision, KnowledgeClass
from trusted_runtime.roles_permissions_track_center import AuthorityBasis, AuthorityStatus, RolePermissionEvent, RolePermissionEventType, process_role_permission_event


def base_claim():
    return RolePermissionEvent(
        event_id="event:scope",
        authority_id="authority:deploy",
        subject_id="agent:release",
        event_type=RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
        authority_status=AuthorityStatus.ACTIVE,
        authority_basis=AuthorityBasis.DIRECT_PERMISSION,
        action="deploy",
        resource="service:payments",
        scope_ref="scope:production",
        knowledge_class=KnowledgeClass.FACT,
        statement="Current claim requires complete scope.",
        occurred_at="2026-06-25T11:10:00Z",
        confidence=0.9,
        repeat_count=1,
        evidence_refs=("evidence:grant",),
        provenance_refs=("provenance:policy",),
        context_refs=("context:production",),
        observer_refs=("observer:security",),
    )


@pytest.mark.parametrize("field", ["action", "resource", "scope_ref"])
def test_incomplete_claim_is_held(field):
    event = replace(base_claim(), **{field: ""})
    result = process_role_permission_event(event, processed_at="2026-06-25T11:11:00Z")
    assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert result.to_dict()["access_grant_allowed"] is False
