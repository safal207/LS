"""Fail-closed checks for OVC -> VerifiedEpisode v0.2."""

from __future__ import annotations

from typing import Any

from ovc_episode_policy import parse_timestamp, stable_episode_id

OUTCOME_REASON_CODES = {
    "expected": "EXPECTED_OUTCOME_VERIFIED",
    "failed": "FAILURE_OUTCOME_VERIFIED",
    "unexpected": "UNEXPECTED_OUTCOME_VERIFIED",
}

EVIDENCE_ROLES = {
    "expected": "supporting",
    "failed": "failure",
    "unexpected": "contradicting",
}

REQUIRED_BINDINGS = (
    "execution_id",
    "action_id",
    "action_digest",
    "actor_id",
    "target_id",
    "side_effect_key",
    "expected_state_digest",
    "verified_state_digest",
    "receipt_id",
    "receipt_digest",
)

REQUIRED_LEARNING_FIELDS = (
    "task_id",
    "trail_id",
    "orientation_ref",
    "transition_id",
    "decision",
    "lesson_statement",
    "lesson_scope",
    "lesson_repeat_key",
    "evidence_role",
)


def run(
    case: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    str,
    list[dict[str, Any]],
    list[tuple[str, str]],
]:
    adapter = case.get("adapter", {})
    ovc = adapter.get("ovc_result", {})
    bindings = adapter.get("bindings", {})
    learning = adapter.get("learning", {})
    lifecycle = adapter.get("lifecycle", {})
    authoritative = case.get("authoritative_state", {})

    checks: list[dict[str, Any]] = []
    faults: list[tuple[str, str]] = []

    def fail(
        check: str,
        verdict: str,
        reason: str,
        **details: Any,
    ) -> None:
        checks.append({"check": check, "status": "failed", **details})
        faults.append((verdict, reason))

    def pass_check(check: str, **details: Any) -> None:
        checks.append({"check": check, "status": "passed", **details})

    if (
        adapter.get("adapter_version") != "ovc-to-verified-episode-v0.1"
        or ovc.get("verification_version") != "outcome-verification-v0.1"
    ):
        fail("version", "REJECT", "UNSUPPORTED_VERSION")
    else:
        pass_check("version")

    unsafe = (
        ovc.get("execution_authorized") is not False
        or ovc.get("retroactive_authorization_created") is not False
        or ovc.get("downstream_learning_gate_required") is not True
    )
    if unsafe:
        fail("ovc_safety", "REJECT", "OVC_SAFETY_INVARIANT_VIOLATION")
    else:
        pass_check("ovc_safety")

    if ovc.get("verdict") != "VERIFIED":
        fail(
            "ovc_verdict",
            "REJECT",
            "OVC_NOT_VERIFIED",
            observed=ovc.get("verdict"),
        )
    else:
        pass_check("ovc_verdict")

    if ovc.get("experience_eligible") is not True:
        fail("experience_eligibility", "REJECT", "EXPERIENCE_NOT_ELIGIBLE")
    else:
        pass_check("experience_eligibility")

    missing_bindings = [
        field
        for field in REQUIRED_BINDINGS
        if bindings.get(field) in (None, "")
    ]
    if missing_bindings:
        fail(
            "identity_bindings",
            "REJECT",
            "MISSING_IDENTITY_BINDING",
            missing=missing_bindings,
        )
    else:
        pass_check("identity_bindings")

    if (
        bindings.get("causal_trace_id") in (None, "")
        or not bindings.get("observer_evidence_digests")
        or not bindings.get("source_event_ids")
    ):
        fail("provenance", "REJECT", "MISSING_PROVENANCE")
    else:
        pass_check("provenance")

    state_is_bound = (
        ovc.get("verified_state_digest")
        == bindings.get("verified_state_digest")
        and ovc.get("new_orientation_state_digest_candidate")
        == bindings.get("verified_state_digest")
    )
    if not state_is_bound:
        fail(
            "verified_state_binding",
            "REJECT",
            "MISSING_IDENTITY_BINDING",
        )
    else:
        pass_check("verified_state_binding")

    expected_reason = OUTCOME_REASON_CODES.get(ovc.get("outcome_class"))
    if expected_reason is None or ovc.get("reason_code") != expected_reason:
        fail(
            "ovc_outcome_reason",
            "REVIEW",
            "OVC_OUTCOME_REASON_MISMATCH",
            expected=expected_reason,
            observed=ovc.get("reason_code"),
        )
    else:
        pass_check("ovc_outcome_reason")

    missing_learning = [
        field
        for field in REQUIRED_LEARNING_FIELDS
        if learning.get(field) in (None, "")
    ]
    confidence = learning.get("lesson_confidence")
    if missing_learning or not isinstance(confidence, (int, float)):
        fail(
            "learning_contract",
            "ABSTAIN",
            "MISSING_LESSON_EVIDENCE",
            missing=missing_learning,
        )
    else:
        pass_check("learning_contract")

    expected_role = EVIDENCE_ROLES.get(ovc.get("outcome_class"))
    if learning.get("evidence_role") != expected_role:
        fail(
            "lesson_role",
            "REVIEW",
            "LESSON_OUTCOME_MISMATCH",
            expected=expected_role,
            observed=learning.get("evidence_role"),
        )
    else:
        pass_check("lesson_role")

    try:
        created_at = parse_timestamp(lifecycle["created_at"])
        review_after = parse_timestamp(lifecycle["review_after"])
        current_time = parse_timestamp(authoritative["current_time"])
        expires_at = (
            parse_timestamp(lifecycle["expires_at"])
            if lifecycle.get("expires_at")
            else None
        )

        invalid_window = review_after < created_at or (
            expires_at is not None and expires_at < review_after
        )
        if invalid_window:
            fail("retention_window", "REJECT", "INVALID_RETENTION_WINDOW")
        else:
            pass_check("retention_window")

        if expires_at is not None and current_time >= expires_at:
            fail("retention_expiry", "FORGET", "RETENTION_EXPIRED")
        else:
            pass_check("retention_expiry")
    except (KeyError, TypeError, ValueError):
        fail("retention_window", "REJECT", "INVALID_RETENTION_WINDOW")

    if lifecycle.get("redaction_state") == "redacted":
        required = set(authoritative.get("required_unredacted_fields", []))
        redactable = set(lifecycle.get("redactable_fields", []))
        overlap = required & redactable
        if overlap:
            fail(
                "redaction",
                "ABSTAIN",
                "REDACTION_INCOMPLETE",
                fields=sorted(overlap),
            )
        else:
            pass_check("redaction")
    else:
        pass_check("redaction")

    identity = {
        "execution_id": bindings.get("execution_id"),
        "action_digest": bindings.get("action_digest"),
        "side_effect_key": bindings.get("side_effect_key"),
        "causal_trace_id": bindings.get("causal_trace_id"),
        "outcome_class": ovc.get("outcome_class"),
        "verified_state_digest": bindings.get("verified_state_digest"),
        "lesson_repeat_key": learning.get("lesson_repeat_key"),
    }
    episode_id = stable_episode_id(identity)

    if episode_id in set(authoritative.get("seen_episode_ids", [])):
        fail(
            "episode_replay",
            "REJECT",
            "EPISODE_REPLAY",
            episode_id=episode_id,
        )
    else:
        pass_check("episode_replay")

    if bindings.get("causal_trace_id") in set(
        authoritative.get("seen_causal_trace_ids", [])
    ):
        fail("causal_trace_replay", "REJECT", "CAUSAL_TRACE_REPLAY")
    else:
        pass_check("causal_trace_replay")

    return (
        ovc,
        bindings,
        learning,
        lifecycle,
        episode_id,
        checks,
        faults,
    )
