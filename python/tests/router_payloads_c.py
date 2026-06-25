from __future__ import annotations


def role_payload() -> dict[str, object]:
    return {
        "schema_version": "trusted_runtime.role_permission_event.v0.1",
        "event_id": "authority-event:router",
        "authority_id": "authority:deploy-production",
        "subject_id": "agent:release-bot",
        "event_type": "AUTHORIZATION_PATTERN_VERIFIED",
        "authority_status": "ACTIVE",
        "authority_basis": "DIRECT_PERMISSION",
        "action": "deploy",
        "resource": "service:payments",
        "scope_ref": "scope:production",
        "knowledge_class": "FACT",
        "statement": "Authorization evidence repeated across contexts.",
        "occurred_at": "2026-06-25T11:40:00Z",
        "confidence": 0.95,
        "repeat_count": 2,
        "evidence_refs": ["evidence:role:1", "evidence:role:2"],
        "provenance_refs": ["provenance:policy:1", "provenance:policy:2"],
        "context_refs": ["context:staging", "context:production"],
        "observer_refs": ["observer:security", "observer:release"],
        "role_refs": ["role:release-operator"],
        "approval_refs": [],
        "identity_candidate_statement": "Escalate when authority scope is incomplete.",
        "identity_scope": "roles.permissions",
        "identity_repeat_key": "authority:escalate-incomplete",
        "metadata": {},
    }
