"""Fail-closed checks for OVC -> VerifiedEpisode v0.2."""
from __future__ import annotations
from typing import Any
from ovc_episode_policy import parse_ts,stable_id

REASONS={"expected":"EXPECTED_OUTCOME_VERIFIED","failed":"FAILURE_OUTCOME_VERIFIED","unexpected":"UNEXPECTED_OUTCOME_VERIFIED"}
ROLES={"expected":"supporting","failed":"failure","unexpected":"contradicting"}
BINDINGS=("execution_id","action_id","action_digest","actor_id","target_id","side_effect_key","expected_state_digest","verified_state_digest","receipt_id","receipt_digest")
LEARNING=("task_id","trail_id","orientation_ref","transition_id","decision","lesson_statement","lesson_scope","lesson_repeat_key","evidence_role")

def run(case:dict[str,Any]):
    a=case.get("adapter",{});o=a.get("ovc_result",{});b=a.get("bindings",{})
    l=a.get("learning",{});life=a.get("lifecycle",{});auth=case.get("authoritative_state",{})
    checks=[];faults=[]
    def bad(name,v,r,**d):checks.append({"check":name,"status":"failed",**d});faults.append((v,r))
    def ok(name,**d):checks.append({"check":name,"status":"passed",**d})

    if a.get("adapter_version")!="ovc-to-verified-episode-v0.1" or o.get("verification_version")!="outcome-verification-v0.1":bad("version","REJECT","UNSUPPORTED_VERSION")
    else:ok("version")

    unsafe=o.get("execution_authorized") is not False or o.get("retroactive_authorization_created") is not False or o.get("downstream_learning_gate_required") is not True
    if unsafe:bad("ovc_safety","REJECT","OVC_SAFETY_INVARIANT_VIOLATION")
    else:ok("ovc_safety")

    if o.get("verdict")!="VERIFIED":bad("ovc_verdict","REJECT","OVC_NOT_VERIFIED",observed=o.get("verdict"))
    else:ok("ovc_verdict")
    if o.get("experience_eligible") is not True:bad("experience_eligibility","REJECT","EXPERIENCE_NOT_ELIGIBLE")
    else:ok("experience_eligibility")

    missing=[x for x in BINDINGS if b.get(x) in (None,"")]
    if missing:bad("identity_bindings","REJECT","MISSING_IDENTITY_BINDING",missing=missing)
    else:ok("identity_bindings")
    if b.get("causal_trace_id") in (None,"") or not b.get("observer_evidence_digests") or not b.get("source_event_ids"):bad("provenance","REJECT","MISSING_PROVENANCE")
    else:ok("provenance")

    bound=o.get("verified_state_digest")==b.get("verified_state_digest") and o.get("new_orientation_state_digest_candidate")==b.get("verified_state_digest")
    if not bound:bad("verified_state_binding","REJECT","MISSING_IDENTITY_BINDING")
    else:ok("verified_state_binding")

    expected_reason=REASONS.get(o.get("outcome_class"))
    if expected_reason is None or o.get("reason_code")!=expected_reason:bad("ovc_outcome_reason","REVIEW","OVC_OUTCOME_REASON_MISMATCH",expected=expected_reason,observed=o.get("reason_code"))
    else:ok("ovc_outcome_reason")

    missing_l=[x for x in LEARNING if l.get(x) in (None,"")]
    if missing_l or not isinstance(l.get("lesson_confidence"),(int,float)):bad("learning_contract","ABSTAIN","MISSING_LESSON_EVIDENCE",missing=missing_l)
    else:ok("learning_contract")
    expected_role=ROLES.get(o.get("outcome_class"))
    if l.get("evidence_role")!=expected_role:bad("lesson_role","REVIEW","LESSON_OUTCOME_MISMATCH",expected=expected_role,observed=l.get("evidence_role"))
    else:ok("lesson_role")

    try:
        created=parse_ts(life["created_at"]);review=parse_ts(life["review_after"]);now=parse_ts(auth["current_time"])
        expires=parse_ts(life["expires_at"]) if life.get("expires_at") else None
        if review<created or (expires and expires<review):bad("retention_window","REJECT","INVALID_RETENTION_WINDOW")
        else:ok("retention_window")
        if expires and now>=expires:bad("retention_expiry","FORGET","RETENTION_EXPIRED")
        else:ok("retention_expiry")
    except Exception:bad("retention_window","REJECT","INVALID_RETENTION_WINDOW")

    if life.get("redaction_state")=="redacted":
        overlap=set(auth.get("required_unredacted_fields",[]))&set(life.get("redactable_fields",[]))
        if overlap:bad("redaction","ABSTAIN","REDACTION_INCOMPLETE",fields=sorted(overlap))
        else:ok("redaction")
    else:ok("redaction")

    identity={"execution_id":b.get("execution_id"),"action_digest":b.get("action_digest"),"side_effect_key":b.get("side_effect_key"),"causal_trace_id":b.get("causal_trace_id"),"outcome_class":o.get("outcome_class"),"verified_state_digest":b.get("verified_state_digest"),"lesson_repeat_key":l.get("lesson_repeat_key")}
    eid=stable_id(identity)
    if eid in set(auth.get("seen_episode_ids",[])):bad("episode_replay","REJECT","EPISODE_REPLAY",episode_id=eid)
    else:ok("episode_replay")
    if b.get("causal_trace_id") in set(auth.get("seen_causal_trace_ids",[])):bad("causal_trace_replay","REJECT","CAUSAL_TRACE_REPLAY")
    else:ok("causal_trace_replay")
    return o,b,l,life,eid,checks,faults
