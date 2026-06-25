from __future__ import annotations

from typing import Optional


def payload_a(route: str) -> Optional[dict[str, object]]:
    if route == "relationships.loss":
        return {
            "schema_version": "trusted_runtime.relationship_loss_event.v0.1",
            "event_id": "relationship-event:router",
            "relationship_id": "relationship:mentor",
            "subject_id": "human:mentor",
            "event_type": "REMEMBERED_INFLUENCE",
            "entity_status": "DECEASED",
            "knowledge_class": "MEMORY",
            "statement": "Remembered discipline remains influential.",
            "occurred_at": "2026-06-25T05:00:00Z",
            "confidence": 0.86,
            "evidence_refs": ["memory:mentor:review"],
            "identity_candidate_statement": "Preserve evidence-first reviews.",
            "identity_scope": "relationships",
            "identity_repeat_key": "mentor:evidence-first",
            "metadata": {},
        }
    if route == "projects.lifecycle":
        return {
            "schema_version": "trusted_runtime.project_event.v0.1",
            "event_id": "project-event:router",
            "project_id": "project:ls",
            "event_type": "PROJECT_LESSON_RETAINED",
            "project_status": "COMPLETED",
            "previous_status": None,
            "knowledge_class": "MEMORY",
            "statement": "A bounded project lesson.",
            "occurred_at": "2026-06-25T05:00:00Z",
            "confidence": 0.91,
            "evidence_refs": ["evidence:project"],
            "identity_candidate_statement": "Preserve evidence-first delivery.",
            "identity_scope": "projects",
            "identity_repeat_key": "project:ls:evidence-first",
            "metadata": {},
        }
    if route == "values.evidence":
        return {
            "schema_version": "trusted_runtime.value_event.v0.1",
            "event_id": "value-event:router",
            "value_key": "value:evidence-first",
            "event_type": "VALUE_REAFFIRMED",
            "value_status": "ACTIVE",
            "knowledge_class": "FACT",
            "statement": "Evidence should precede confident conclusions.",
            "occurred_at": "2026-06-25T05:00:00Z",
            "confidence": 0.92,
            "repeat_count": 3,
            "evidence_refs": ["evidence:value:work", "evidence:value:family"],
            "context_refs": ["context:work", "context:family"],
            "identity_candidate_statement": "Prefer evidence before conclusions.",
            "identity_scope": "values",
            "identity_repeat_key": "value:evidence-first",
            "metadata": {},
        }
    return None
