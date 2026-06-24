"""Build a VerifiedEpisode v0.2 candidate."""

from __future__ import annotations

from typing import Any


def build(
    ovc: dict[str, Any],
    bindings: dict[str, Any],
    learning: dict[str, Any],
    lifecycle: dict[str, Any],
    episode_id: str,
) -> dict[str, Any]:
    outcome_class = ovc["outcome_class"]
    expected_v01 = outcome_class == "expected"

    provenance = {
        "verification_version": ovc["verification_version"],
        "verification_reason_code": ovc["reason_code"],
        "execution_id": bindings["execution_id"],
        "action_id": bindings["action_id"],
        "action_digest": bindings["action_digest"],
        "actor_id": bindings["actor_id"],
        "target_id": bindings["target_id"],
        "side_effect_key": bindings["side_effect_key"],
        "receipt_id": bindings["receipt_id"],
        "receipt_digest": bindings["receipt_digest"],
        "causal_trace_id": bindings["causal_trace_id"],
        "observer_evidence_digests": list(
            dict.fromkeys(bindings["observer_evidence_digests"])
        ),
        "source_event_ids": list(
            dict.fromkeys(bindings["source_event_ids"])
        ),
    }
    lesson = {
        "statement": learning["lesson_statement"],
        "scope": learning["lesson_scope"],
        "confidence": learning["lesson_confidence"],
        "repeat_key": learning["lesson_repeat_key"],
        "evidence_role": learning["evidence_role"],
        "evidence_refs": provenance["observer_evidence_digests"],
    }
    lifecycle_output = {
        "retention_class": lifecycle["retention_class"],
        "review_after": lifecycle["review_after"],
        "expires_at": lifecycle.get("expires_at"),
        "redactable_fields": lifecycle.get("redactable_fields", []),
        "redaction_state": lifecycle["redaction_state"],
        "supersedes_episode_id": lifecycle.get("supersedes_episode_id"),
    }

    return {
        "schema_version": "trusted_runtime.verified_episode.v0.2",
        "episode_id": episode_id,
        "task_id": learning["task_id"],
        "trail_id": learning["trail_id"],
        "orientation_ref": learning["orientation_ref"],
        "transition_id": learning["transition_id"],
        "decision": learning["decision"],
        "created_at": lifecycle["created_at"],
        "status": "VERIFIED",
        "outcome_class": outcome_class,
        "expected_state_digest": bindings["expected_state_digest"],
        "verified_state_digest": bindings["verified_state_digest"],
        "provenance": provenance,
        "lesson": lesson,
        "lifecycle": lifecycle_output,
        "experience_eligible": True,
        "identity_update_eligible": False,
        "identity_update": {
            "allowed": False,
            "applied": False,
            "reason": "single_verified_episode_cannot_modify_stable_identity",
            "policy_version": "identity_update.single_episode.v0.2",
            "minimum_verified_episodes": 3,
            "current_verified_episodes": 1,
        },
        "v0_1_projection": {
            "schema_version": "trusted_runtime.verified_episode.v0.1",
            "status": "VERIFIED" if expected_v01 else "UNVERIFIED",
            "outcome_status": "MATCHED" if expected_v01 else "MISMATCHED",
        },
    }
