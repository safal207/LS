#!/usr/bin/env python3
"""Deterministic evaluator for LS Precise Action Temporal Orientation Center v0.1."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEVERITY = {
    "EXECUTE_CANDIDATE": 0,
    "ABSTAIN": 1,
    "WAIT": 2,
    "REVALIDATE": 3,
    "REJECT": 4,
}

REASON_ORDER = {
    "REJECT": [
        "WORKSPACE_MISMATCH",
        "TRAJECTORY_MISMATCH",
        "CONTINUATION_MISMATCH",
        "RELATIONSHIP_MISMATCH",
        "WRONG_ACTOR",
        "WRONG_TARGET",
        "ACTION_DIGEST_MISMATCH",
        "IMMUTABLE_FIELD_CHANGED",
        "PARAMETER_SUBSTITUTION",
        "ACTION_OUT_OF_SEQUENCE",
        "ACTION_ALREADY_COMPLETED",
        "REPLAY_POLICY_VIOLATION",
        "ACTION_WINDOW_EXPIRED",
    ],
    "REVALIDATE": [
        "EXPECTED_ACTION_CHANGED",
        "TARGET_STATE_DRIFT",
        "CURRENT_STATE_DIGEST_MISMATCH",
        "PARAMETERS_STALE",
        "SEQUENCE_POSITION_DRIFT",
        "DEADLINE_CHANGED",
        "EXPECTED_TRANSITION_CHANGED",
        "VERIFICATION_CONTRACT_CHANGED",
    ],
    "WAIT": [
        "SCHEDULE_NOT_REACHED",
        "REQUIRED_EVENT_NOT_OCCURRED",
        "APPROVAL_PENDING",
        "PREDECESSOR_NOT_COMPLETED",
        "PRECONDITION_NOT_YET_SATISFIED",
        "SIDE_EFFECT_VERIFICATION_REQUIRED",
    ],
    "ABSTAIN": [
        "AMBIGUOUS_ACTION",
        "MISSING_PARAMETER",
        "INCOMPLETE_DEPENDENCY_CHAIN",
        "UNKNOWN_PRECONDITION_STATE",
        "MISSING_VERIFICATION_CONTRACT",
        "INVALID_TIME_EVIDENCE",
    ],
}


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _get_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _result(
    fixture_id: str,
    verdict: str,
    reason_code: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "action_orientation_version": "precise-action-temporal-orientation-v0.1",
        "verdict": verdict,
        "reason_code": reason_code,
        "execution_authorized": False,
        "downstream_gates_required": True,
        "checks": checks,
    }


def _choose_fault(faults: list[tuple[str, str]]) -> tuple[str, str]:
    if not faults:
        return "EXECUTE_CANDIDATE", "PRECISE_ACTION_ORIENTATION_VALID"

    highest = max(SEVERITY[verdict] for verdict, _ in faults)
    verdict = next(name for name, value in SEVERITY.items() if value == highest)
    reasons = {reason for candidate, reason in faults if candidate == verdict}
    for reason in REASON_ORDER[verdict]:
        if reason in reasons:
            return verdict, reason
    return verdict, sorted(reasons)[0]


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    fixture_id = case.get("fixture_id", "unknown")
    checks: list[dict[str, Any]] = []
    faults: list[tuple[str, str]] = []

    orientation = case.get("orientation", {})
    context = orientation.get("context", {})
    identity = orientation.get("action_identity", {})
    temporal = orientation.get("temporal_position", {})
    parameters = orientation.get("parameters", {})
    dependencies = orientation.get("dependencies", {})
    side_effect = orientation.get("side_effect_control", {})
    transition = orientation.get("expected_transition", {})
    verification = orientation.get("verification", {})
    authoritative = case.get("authoritative_state", {})
    proposed = case.get("proposed_action", {})

    def fault(check: str, verdict: str, reason: str, **details: Any) -> None:
        checks.append({"check": check, "status": "failed", **details})
        faults.append((verdict, reason))

    def passed(check: str, **details: Any) -> None:
        checks.append({"check": check, "status": "passed", **details})

    required_identity = {
        "orientation.action_identity.action_id": identity.get("action_id"),
        "orientation.action_identity.action_digest": identity.get("action_digest"),
        "orientation.action_identity.actor_id": identity.get("actor_id"),
        "orientation.action_identity.target_id": identity.get("target_id"),
        "proposed_action.action_id": proposed.get("action_id"),
        "proposed_action.action_digest": proposed.get("action_digest"),
        "proposed_action.actor_id": proposed.get("actor_id"),
        "proposed_action.target_id": proposed.get("target_id"),
        "proposed_action.sequence_index": proposed.get("sequence_index"),
    }
    missing_identity = [
        path for path, value in required_identity.items()
        if value is None or value == ""
    ]
    if missing_identity:
        fault(
            "action_identity_completeness",
            "ABSTAIN",
            "AMBIGUOUS_ACTION",
            missing=missing_identity,
        )
    else:
        passed("action_identity_completeness")

    parameter_digest = proposed.get("parameter_digest")
    exact_arguments = proposed.get("exact_arguments")
    if parameter_digest in (None, "") or not isinstance(exact_arguments, dict):
        fault(
            "parameter_completeness",
            "ABSTAIN",
            "MISSING_PARAMETER",
            missing=[
                name for name, value in {
                    "proposed_action.parameter_digest": parameter_digest,
                    "proposed_action.exact_arguments": exact_arguments,
                }.items()
                if value is None or value == "" or not isinstance(value, dict)
            ],
        )
    else:
        passed("parameter_completeness")

    context_checks = [
        ("workspace", context.get("workspace_id"), authoritative.get("workspace_id"), "WORKSPACE_MISMATCH"),
        ("trajectory", context.get("trajectory_id"), authoritative.get("trajectory_id"), "TRAJECTORY_MISMATCH"),
        (
            "continuation",
            context.get("continuation_id"),
            authoritative.get("active_continuation_id"),
            "CONTINUATION_MISMATCH",
        ),
        (
            "relationship",
            context.get("relationship_id"),
            authoritative.get("relationship_id"),
            "RELATIONSHIP_MISMATCH",
        ),
    ]
    for check_name, observed, expected, reason in context_checks:
        if expected is not None and observed != expected:
            fault(
                f"{check_name}_context",
                "REJECT",
                reason,
                observed=observed,
                expected=expected,
            )
        else:
            passed(f"{check_name}_context")

    proposed_actor = proposed.get("actor_id")
    if proposed_actor is not None and proposed_actor != identity.get("actor_id"):
        fault(
            "actor_identity",
            "REJECT",
            "WRONG_ACTOR",
            observed=proposed_actor,
            expected=identity.get("actor_id"),
        )
    elif identity.get("actor_id") != authoritative.get("expected_actor_id"):
        fault(
            "authoritative_actor",
            "REVALIDATE",
            "EXPECTED_ACTION_CHANGED",
            observed=identity.get("actor_id"),
            expected=authoritative.get("expected_actor_id"),
        )
    else:
        passed("actor_identity")

    proposed_target = proposed.get("target_id")
    if proposed_target is not None and proposed_target != identity.get("target_id"):
        fault(
            "target_identity",
            "REJECT",
            "WRONG_TARGET",
            observed=proposed_target,
            expected=identity.get("target_id"),
        )
    elif identity.get("target_id") != authoritative.get("expected_target_id"):
        fault(
            "authoritative_target",
            "REVALIDATE",
            "TARGET_STATE_DRIFT",
            observed=identity.get("target_id"),
            expected=authoritative.get("expected_target_id"),
        )
    else:
        passed("target_identity")

    proposed_digest = proposed.get("action_digest")
    if proposed_digest is not None and proposed_digest != identity.get("action_digest"):
        fault(
            "action_digest",
            "REJECT",
            "ACTION_DIGEST_MISMATCH",
            observed=proposed_digest,
            expected=identity.get("action_digest"),
        )
    elif identity.get("action_digest") != authoritative.get("expected_action_digest"):
        fault(
            "authoritative_action_digest",
            "REVALIDATE",
            "EXPECTED_ACTION_CHANGED",
            observed=identity.get("action_digest"),
            expected=authoritative.get("expected_action_digest"),
        )
    else:
        passed("action_digest")

    if proposed.get("action_id") is not None and proposed.get("action_id") != identity.get("action_id"):
        fault(
            "action_id",
            "REJECT",
            "ACTION_DIGEST_MISMATCH",
            observed=proposed.get("action_id"),
            expected=identity.get("action_id"),
        )
    elif identity.get("action_id") != authoritative.get("expected_action_id"):
        fault(
            "authoritative_action_id",
            "REVALIDATE",
            "EXPECTED_ACTION_CHANGED",
            observed=identity.get("action_id"),
            expected=authoritative.get("expected_action_id"),
        )
    else:
        passed("action_id")

    if proposed.get("action_type") is not None and proposed.get("action_type") != identity.get("action_type"):
        fault(
            "action_type",
            "REJECT",
            "ACTION_DIGEST_MISMATCH",
            observed=proposed.get("action_type"),
            expected=identity.get("action_type"),
        )
    elif identity.get("action_type") != authoritative.get("expected_action_type"):
        fault(
            "authoritative_action_type",
            "REVALIDATE",
            "EXPECTED_ACTION_CHANGED",
            observed=identity.get("action_type"),
            expected=authoritative.get("expected_action_type"),
        )
    else:
        passed("action_type")

    authoritative_parameter_digest = authoritative.get("expected_parameter_digest")
    if authoritative_parameter_digest is not None and parameters.get("parameter_digest") != authoritative_parameter_digest:
        fault(
            "parameter_freshness",
            "REVALIDATE",
            "PARAMETERS_STALE",
            observed=parameters.get("parameter_digest"),
            expected=authoritative_parameter_digest,
        )
    else:
        passed("parameter_freshness")

    if parameter_digest is not None and parameter_digest != parameters.get("parameter_digest"):
        fault(
            "parameter_digest",
            "REJECT",
            "PARAMETER_SUBSTITUTION",
            observed=parameter_digest,
            expected=parameters.get("parameter_digest"),
        )
    else:
        passed("parameter_digest")

    if isinstance(exact_arguments, dict):
        immutable_changed = []
        for field in parameters.get("immutable_fields", []):
            expected_value = _get_path(parameters.get("exact_arguments", {}), field)
            observed_value = _get_path(exact_arguments, field)
            if observed_value != expected_value:
                immutable_changed.append({
                    "field": field,
                    "observed": observed_value,
                    "expected": expected_value,
                })
        if immutable_changed:
            fault(
                "immutable_fields",
                "REJECT",
                "IMMUTABLE_FIELD_CHANGED",
                changed=immutable_changed,
            )
        else:
            passed("immutable_fields")

        if exact_arguments != parameters.get("exact_arguments", {}):
            fault(
                "exact_arguments",
                "REJECT",
                "PARAMETER_SUBSTITUTION",
                observed=exact_arguments,
                expected=parameters.get("exact_arguments", {}),
            )
        else:
            passed("exact_arguments")

    authoritative_arguments = authoritative.get("expected_exact_arguments")
    if authoritative_arguments is not None and parameters.get("exact_arguments") != authoritative_arguments:
        fault(
            "authoritative_arguments",
            "REVALIDATE",
            "PARAMETERS_STALE",
            observed=parameters.get("exact_arguments"),
            expected=authoritative_arguments,
        )
    else:
        passed("authoritative_arguments")

    expected_sequence = authoritative.get("next_sequence_index")
    if expected_sequence is not None and temporal.get("sequence_index") != expected_sequence:
        fault(
            "sequence_freshness",
            "REVALIDATE",
            "SEQUENCE_POSITION_DRIFT",
            observed=temporal.get("sequence_index"),
            expected=expected_sequence,
        )
    else:
        passed("sequence_freshness")

    if proposed.get("sequence_index") is not None and proposed.get("sequence_index") != temporal.get("sequence_index"):
        fault(
            "proposed_sequence",
            "REJECT",
            "ACTION_OUT_OF_SEQUENCE",
            observed=proposed.get("sequence_index"),
            expected=temporal.get("sequence_index"),
        )
    else:
        passed("proposed_sequence")

    completed_actions = set(authoritative.get("completed_action_ids", []))
    missing_predecessors = [
        action_id
        for action_id in dependencies.get("previous_action_ids", [])
        if action_id not in completed_actions
    ]
    if missing_predecessors:
        fault(
            "predecessor_completion",
            "WAIT",
            "PREDECESSOR_NOT_COMPLETED",
            missing=missing_predecessors,
        )
    else:
        passed("predecessor_completion")

    try:
        current_time = _parse_timestamp(authoritative["current_time"])
        valid_from = _parse_timestamp(temporal["valid_from"])
        execute_not_before = _parse_timestamp(temporal["execute_not_before"]) if temporal.get("execute_not_before") else None
        deadline_at = _parse_timestamp(temporal["deadline_at"]) if temporal.get("deadline_at") else None
        invalidated_at = _parse_timestamp(temporal["invalidated_at"]) if temporal.get("invalidated_at") else None
    except (KeyError, TypeError, ValueError):
        fault("time_evidence", "ABSTAIN", "INVALID_TIME_EVIDENCE")
    else:
        if current_time < valid_from or (execute_not_before is not None and current_time < execute_not_before):
            fault(
                "schedule",
                "WAIT",
                "SCHEDULE_NOT_REACHED",
                current_time=authoritative.get("current_time"),
                execute_not_before=temporal.get("execute_not_before") or temporal.get("valid_from"),
            )
        else:
            passed("schedule")

        if (deadline_at is not None and current_time > deadline_at) or (invalidated_at is not None and current_time >= invalidated_at):
            fault(
                "action_window",
                "REJECT",
                "ACTION_WINDOW_EXPIRED",
                current_time=authoritative.get("current_time"),
                deadline_at=temporal.get("deadline_at"),
                invalidated_at=temporal.get("invalidated_at"),
            )
        else:
            passed("action_window")

    current_deadline = authoritative.get("expected_deadline_at")
    if current_deadline is not None and temporal.get("deadline_at") != current_deadline:
        fault(
            "deadline_freshness",
            "REVALIDATE",
            "DEADLINE_CHANGED",
            observed=temporal.get("deadline_at"),
            expected=current_deadline,
        )
    else:
        passed("deadline_freshness")

    occurred_events = set(authoritative.get("occurred_event_ids", []))
    missing_events = [event_id for event_id in dependencies.get("required_event_ids", []) if event_id not in occurred_events]
    if missing_events:
        fault("required_events", "WAIT", "REQUIRED_EVENT_NOT_OCCURRED", missing=missing_events)
    else:
        passed("required_events")

    active_approvals = set(authoritative.get("active_approval_ids", []))
    missing_approvals = [approval_id for approval_id in dependencies.get("required_approval_ids", []) if approval_id not in active_approvals]
    if missing_approvals:
        fault("required_approvals", "WAIT", "APPROVAL_PENDING", missing=missing_approvals)
    else:
        passed("required_approvals")

    authoritative_preconditions = authoritative.get("preconditions", {})
    for precondition in orientation.get("preconditions", []):
        precondition_id = precondition.get("precondition_id")
        current = authoritative_preconditions.get(precondition_id)
        if current is None:
            fault("precondition_state", "ABSTAIN", "UNKNOWN_PRECONDITION_STATE", precondition_id=precondition_id)
            continue
        if current.get("state_digest") != precondition.get("required_state_digest"):
            fault(
                "precondition_digest",
                "REVALIDATE",
                "CURRENT_STATE_DIGEST_MISMATCH",
                precondition_id=precondition_id,
                observed=current.get("state_digest"),
                expected=precondition.get("required_state_digest"),
            )
        elif current.get("status") == "unknown":
            fault("precondition_state", "ABSTAIN", "UNKNOWN_PRECONDITION_STATE", precondition_id=precondition_id)
        elif current.get("status") != "satisfied":
            fault(
                "precondition_state",
                "WAIT",
                "PRECONDITION_NOT_YET_SATISFIED",
                precondition_id=precondition_id,
                observed=current.get("status"),
            )
        else:
            passed("precondition_state", precondition_id=precondition_id)

    proposed_side_effect_key = proposed.get("side_effect_key")
    oriented_side_effect_key = side_effect.get("side_effect_key")
    if proposed_side_effect_key is not None and proposed_side_effect_key != oriented_side_effect_key:
        fault(
            "side_effect_identity",
            "REJECT",
            "PARAMETER_SUBSTITUTION",
            observed=proposed_side_effect_key,
            expected=oriented_side_effect_key,
        )
    else:
        passed("side_effect_identity")

    completed_side_effects = set(authoritative.get("completed_side_effect_keys", []))
    already_completed = side_effect.get("completed", False) or (
        oriented_side_effect_key is not None and oriented_side_effect_key in completed_side_effects
    )
    replay_policy = side_effect.get("replay_policy")
    if already_completed and replay_policy == "reject":
        fault(
            "side_effect_replay",
            "REJECT",
            "ACTION_ALREADY_COMPLETED",
            side_effect_key=oriented_side_effect_key,
        )
    elif already_completed and replay_policy in {"idempotent", "verify"}:
        fault(
            "side_effect_replay",
            "WAIT",
            "SIDE_EFFECT_VERIFICATION_REQUIRED",
            side_effect_key=oriented_side_effect_key,
            replay_policy=replay_policy,
        )
    else:
        passed("side_effect_replay")

    if transition.get("current_state_digest") != authoritative.get("current_state_digest"):
        fault(
            "current_state",
            "REVALIDATE",
            "TARGET_STATE_DRIFT",
            observed=transition.get("current_state_digest"),
            expected=authoritative.get("current_state_digest"),
        )
    else:
        passed("current_state")

    if transition.get("expected_state_digest") != authoritative.get("expected_state_digest"):
        fault(
            "expected_transition",
            "REVALIDATE",
            "EXPECTED_TRANSITION_CHANGED",
            observed=transition.get("expected_state_digest"),
            expected=authoritative.get("expected_state_digest"),
        )
    else:
        passed("expected_transition")

    requirements = verification.get("verification_requirements", [])
    if not requirements:
        fault("verification_contract", "ABSTAIN", "MISSING_VERIFICATION_CONTRACT")
    else:
        passed("verification_contract")

    expected_verification_type = authoritative.get("required_verification_type")
    expected_requirements = authoritative.get("required_verification_requirements")
    if (
        expected_verification_type is not None
        and verification.get("verification_type") != expected_verification_type
    ) or (
        expected_requirements is not None
        and set(requirements) != set(expected_requirements)
    ):
        fault(
            "verification_freshness",
            "REVALIDATE",
            "VERIFICATION_CONTRACT_CHANGED",
            observed={
                "verification_type": verification.get("verification_type"),
                "verification_requirements": requirements,
            },
            expected={
                "verification_type": expected_verification_type,
                "verification_requirements": expected_requirements,
            },
        )
    else:
        passed("verification_freshness")

    verdict, reason_code = _choose_fault(faults)
    return _result(fixture_id, verdict, reason_code, checks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Fixture JSON file or suite containing cases")
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
