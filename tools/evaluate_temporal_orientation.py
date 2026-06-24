#!/usr/bin/env python3
"""Deterministic evaluator for LS Temporal Orientation Center v0.1."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _result(
    fixture_id: str,
    verdict: str,
    reason_code: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "orientation_version": "temporal-orientation-v0.1",
        "verdict": verdict,
        "reason_code": reason_code,
        "execution_authorized": False,
        "downstream_gates_required": True,
        "checks": checks,
    }


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    fixture_id = case.get("fixture_id", "unknown")
    checks: list[dict[str, Any]] = []

    required_paths = [
        ("orientation.location.workspace_id", case.get("orientation", {}).get("location", {}).get("workspace_id")),
        ("orientation.location.trajectory_id", case.get("orientation", {}).get("location", {}).get("trajectory_id")),
        ("orientation.location.continuation_id", case.get("orientation", {}).get("location", {}).get("continuation_id")),
        ("orientation.current_frame.as_of", case.get("orientation", {}).get("current_frame", {}).get("as_of")),
        ("orientation.current_frame.intent_digest", case.get("orientation", {}).get("current_frame", {}).get("intent_digest")),
        ("orientation.current_frame.target_state_digest", case.get("orientation", {}).get("current_frame", {}).get("target_state_digest")),
        ("authoritative_state.workspace_id", case.get("authoritative_state", {}).get("workspace_id")),
        ("authoritative_state.trajectory_id", case.get("authoritative_state", {}).get("trajectory_id")),
        ("authoritative_state.active_continuation_id", case.get("authoritative_state", {}).get("active_continuation_id")),
        ("proposed_action.action_digest", case.get("proposed_action", {}).get("action_digest")),
    ]
    missing = [path for path, value in required_paths if value in (None, "")]
    if missing:
        checks.append({"check": "required_evidence", "status": "failed", "missing": missing})
        return _result(fixture_id, "ABSTAIN", "MISSING_REQUIRED_EVIDENCE", checks)
    checks.append({"check": "required_evidence", "status": "passed"})

    orientation = case["orientation"]
    location = orientation["location"]
    frame = orientation["current_frame"]
    authority = orientation.get("active_authority", {})
    history = orientation.get("completed_history", {})
    validity = orientation.get("validity", {})
    authoritative = case["authoritative_state"]
    action = case["proposed_action"]

    reject_checks = [
        ("workspace_match", location["workspace_id"], authoritative["workspace_id"], "WORKSPACE_MISMATCH"),
        ("trajectory_match", location["trajectory_id"], authoritative["trajectory_id"], "TRAJECTORY_MISMATCH"),
        ("continuation_match", location["continuation_id"], authoritative["active_continuation_id"], "CONTINUATION_MISMATCH"),
        ("intent_match", frame["intent_digest"], authoritative.get("current_intent_digest"), "INTENT_MISMATCH"),
    ]
    for name, observed, expected, reason in reject_checks:
        if expected is not None and observed != expected:
            checks.append({"check": name, "status": "failed", "observed": observed, "expected": expected})
            return _result(fixture_id, "REJECT", reason, checks)
        checks.append({"check": name, "status": "passed"})

    if action.get("requires_approval", False):
        if authority.get("approval_state") != "active":
            checks.append({
                "check": "approval_state",
                "status": "failed",
                "observed": authority.get("approval_state", "absent"),
                "expected": "active",
            })
            return _result(fixture_id, "REJECT", "APPROVAL_NOT_ACTIVE", checks)
        if authority.get("approval_id") != authoritative.get("active_approval_id"):
            checks.append({
                "check": "approval_identity",
                "status": "failed",
                "observed": authority.get("approval_id"),
                "expected": authoritative.get("active_approval_id"),
            })
            return _result(fixture_id, "REJECT", "APPROVAL_MISMATCH", checks)
        checks.append({"check": "approval", "status": "passed"})

    side_effect_key = action.get("side_effect_key")
    authoritative_completed = set(authoritative.get("completed_side_effect_keys", []))
    recovered_completed = set(history.get("completed_side_effect_keys", []))
    if side_effect_key and side_effect_key in authoritative_completed.union(recovered_completed):
        checks.append({"check": "side_effect_replay", "status": "failed", "side_effect_key": side_effect_key})
        return _result(fixture_id, "REJECT", "SIDE_EFFECT_ALREADY_COMPLETED", checks)
    checks.append({"check": "side_effect_replay", "status": "passed"})

    current_target = authoritative.get("current_target_state_digest")
    if current_target is not None and frame["target_state_digest"] != current_target:
        checks.append({
            "check": "target_state",
            "status": "failed",
            "observed": frame["target_state_digest"],
            "expected": current_target,
        })
        return _result(fixture_id, "REVALIDATE", "TARGET_STATE_DRIFT", checks)
    checks.append({"check": "target_state", "status": "passed"})

    try:
        as_of = _parse_timestamp(frame["as_of"])
        valid_from = _parse_timestamp(validity["valid_from"]) if validity.get("valid_from") else None
        invalidated_at = _parse_timestamp(validity["invalidated_at"]) if validity.get("invalidated_at") else None
    except (TypeError, ValueError):
        checks.append({"check": "validity_window", "status": "failed", "detail": "invalid timestamp"})
        return _result(fixture_id, "ABSTAIN", "INVALID_VALIDITY_TIMESTAMP", checks)

    if valid_from and as_of < valid_from:
        checks.append({"check": "validity_window", "status": "failed", "detail": "not yet valid"})
        return _result(fixture_id, "REVALIDATE", "ORIENTATION_NOT_YET_VALID", checks)
    if invalidated_at and as_of >= invalidated_at:
        checks.append({"check": "validity_window", "status": "failed", "detail": "invalidated"})
        return _result(fixture_id, "REVALIDATE", "ORIENTATION_INVALIDATED", checks)
    checks.append({"check": "validity_window", "status": "passed"})

    if action.get("requires_complete_dependency_chain", False) and not orientation.get("dependency_chain_complete", False):
        checks.append({"check": "dependency_chain", "status": "failed"})
        return _result(fixture_id, "ABSTAIN", "INCOMPLETE_DEPENDENCY_CHAIN", checks)
    checks.append({"check": "dependency_chain", "status": "passed"})

    allowed_digest = orientation.get("next_transition", {}).get("allowed_next_action_digest")
    if allowed_digest and allowed_digest != action["action_digest"]:
        checks.append({
            "check": "action_digest",
            "status": "failed",
            "observed": action["action_digest"],
            "expected": allowed_digest,
        })
        return _result(fixture_id, "REJECT", "ACTION_DIGEST_MISMATCH", checks)
    checks.append({"check": "action_digest", "status": "passed"})

    return _result(fixture_id, "RESUME", "ORIENTATION_VALID", checks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Fixture JSON file or suite containing a cases array")
    parser.add_argument("--check-expected", action="store_true", help="Exit non-zero when expected output differs")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    cases = payload.get("cases", [payload])
    results = []
    failures = []

    for case in cases:
        result = evaluate(case)
        results.append(result)
        expected = case.get("expected", {})
        if args.check_expected and (
            result["verdict"] != expected.get("verdict")
            or result["reason_code"] != expected.get("reason_code")
        ):
            failures.append({
                "fixture_id": case.get("fixture_id"),
                "expected": expected,
                "actual": {
                    "verdict": result["verdict"],
                    "reason_code": result["reason_code"],
                },
            })

    print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
