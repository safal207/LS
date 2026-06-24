"""Build VerifiedEpisode v0.2 output."""
from __future__ import annotations
from typing import Any

def build(ovc:dict[str,Any],b:dict[str,Any],l:dict[str,Any],life:dict[str,Any],episode_id:str)->dict[str,Any]:
    outcome=ovc["outcome_class"]
    return {
      "schema_version":"trusted_runtime.verified_episode.v0.2","episode_id":episode_id,
      "task_id":l["task_id"],"trail_id":l["trail_id"],"orientation_ref":l["orientation_ref"],
      "transition_id":l["transition_id"],"decision":l["decision"],"created_at":life["created_at"],
      "status":"VERIFIED","outcome_class":outcome,
      "expected_state_digest":b["expected_state_digest"],"verified_state_digest":b["verified_state_digest"],
      "provenance":{
        "verification_version":ovc["verification_version"],"verification_reason_code":ovc["reason_code"],
        "execution_id":b["execution_id"],"action_id":b["action_id"],"action_digest":b["action_digest"],
        "actor_id":b["actor_id"],"target_id":b["target_id"],"side_effect_key":b["side_effect_key"],
        "receipt_id":b["receipt_id"],"receipt_digest":b["receipt_digest"],"causal_trace_id":b["causal_trace_id"],
        "observer_evidence_digests":list(dict.fromkeys(b["observer_evidence_digests"])),
        "source_event_ids":list(dict.fromkeys(b["source_event_ids"])),
      },
      "lesson":{
        "statement":l["lesson_statement"],"scope":l["lesson_scope"],"confidence":l["lesson_confidence"],
        "repeat_key":l["lesson_repeat_key"],"evidence_role":l["evidence_role"],
        "evidence_refs":list(dict.fromkeys(b["observer_evidence_digests"])),
      },
      "lifecycle":{
        "retention_class":life["retention_class"],"review_after":life["review_after"],
        "expires_at":life.get("expires_at"),"redactable_fields":life.get("redactable_fields",[]),
        "redaction_state":life["redaction_state"],"supersedes_episode_id":life.get("supersedes_episode_id"),
      },
      "experience_eligible":True,"identity_update_eligible":False,
      "identity_update":{"allowed":False,"applied":False,
        "reason":"single_verified_episode_cannot_modify_stable_identity",
        "policy_version":"identity_update.single_episode.v0.2",
        "minimum_verified_episodes":3,"current_verified_episodes":1},
      "v0_1_projection":{
        "schema_version":"trusted_runtime.verified_episode.v0.1",
        "status":"VERIFIED" if outcome=="expected" else "UNVERIFIED",
        "outcome_status":"MATCHED" if outcome=="expected" else "MISMATCHED"},
    }
