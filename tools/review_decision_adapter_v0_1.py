#!/usr/bin/env python3
"""Safe projection adapter for coarse ReviewDecision-style runtime signals.

The adapter never invents a user decision. Lifecycle-loss signals update only
requester or presentation state, while ambiguous or malformed inputs fail closed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    ROOT
    / "fixtures"
    / "trusted-runtime"
    / "durable-approval"
    / "review_decision_adapter_cases_v0.1.json"
)

SIGNALS = {
    "USER_APPROVED",
    "USER_REJECTED",
    "REQUESTER_CANCELLED",
    "REQUESTER_DETACHED",
    "TRANSPORT_DISCONNECTED",
    "UI_DISMISSED",
    "WAIT_WINDOW_ELAPSED",
    "POLICY_EXPIRED",
    "CONTEXT_INVALIDATED",
    "STATE_LOST",
}

REQUIRED_CASES = {
    "explicit_user_approval",
    "explicit_user_rejection",
    "requester_cancelled",
    "requester_detached",
    "transport_disconnected",
    "ui_dismissed",
    "wait_elapsed_without_expiry",
    "configured_policy_expiry",
    "verified_context_invalidation",
    "durable_state_loss",
}

INPUT_FIELDS = {
    "approval_id",
    "signal",
    "actor",
    "reason",
    "evidence_ref",
    "exact_bindings_match",
    "expiry_policy_configured",
}

ACTOR_OWNERS = {
    "USER_APPROVED": {"USER", "REVIEWER"},
    "USER_REJECTED": {"USER", "REVIEWER"},
    "REQUESTER_CANCELLED": {"AGENT", "RUNTIME"},
    "REQUESTER_DETACHED": {"AGENT", "RUNTIME"},
    "TRANSPORT_DISCONNECTED": {"TRANSPORT"},
    "UI_DISMISSED": {"USER", "RUNTIME"},
    "WAIT_WINDOW_ELAPSED": {"RUNTIME"},
    "POLICY_EXPIRED": {"POLICY"},
    "CONTEXT_INVALIDATED": {"RUNTIME", "VERIFIER"},
    "STATE_LOST": {"RUNTIME"},
}

EVIDENCE_REQUIRED = {
    "POLICY_EXPIRED",
    "CONTEXT_INVALIDATED",
    "STATE_LOST",
}

EVENT_TYPES = {
    "USER_APPROVED": "UserApproved",
    "USER_REJECTED": "UserRejected",
    "REQUESTER_CANCELLED": "RequesterCancelled",
    "REQUESTER_DETACHED": "RequesterDetached",
    "TRANSPORT_DISCONNECTED": "TransportDisconnected",
    "UI_DISMISSED": "UiDismissed",
    "WAIT_WINDOW_ELAPSED": "WaitWindowElapsed",
    "POLICY_EXPIRED": "ApprovalExpired",
    "CONTEXT_INVALIDATED": "ApprovalInvalidated",
    "STATE_LOST": "LostStateDetected",
}

MESSAGES = {
    "USER_APPROVED": "Approved for the exact reviewed action. Nothing has executed yet.",
    "USER_REJECTED": "You rejected this action. Nothing was executed.",
    "REQUESTER_CANCELLED": "Your decision is still pending. The agent stopped waiting. Nothing was executed.",
    "REQUESTER_DETACHED": "Your decision is still pending. The requester detached. Nothing was executed.",
    "TRANSPORT_DISCONNECTED": "Connection lost. Your pending decision was preserved. Nothing was executed.",
    "UI_DISMISSED": "The approval view was closed. Your decision is still pending. Nothing was executed.",
    "WAIT_WINDOW_ELAPSED": "Still waiting for your decision. Nothing was executed.",
    "POLICY_EXPIRED": "This approval expired under its configured policy. Nothing was executed.",
    "CONTEXT_INVALIDATED": "The action changed. Review and approve the new version. Nothing was executed.",
    "STATE_LOST": "Approval state could not be verified. Nothing will execute without a new decision.",
}

OUTWARD_STATUS = {
    "USER_APPROVED": "APPROVED",
    "USER_REJECTED": "REJECTED_BY_USER",
    "REQUESTER_CANCELLED": "WAITING_FOR_USER",
    "REQUESTER_DETACHED": "WAITING_FOR_USER",
    "TRANSPORT_DISCONNECTED": "CONNECTION_LOST_PENDING",
    "UI_DISMISSED": "PENDING_DECISION_HIDDEN",
    "WAIT_WINDOW_ELAPSED": "WAITING_FOR_USER",
    "POLICY_EXPIRED": "EXPIRED",
    "CONTEXT_INVALIDATED": "REVIEW_REQUIRED",
    "STATE_LOST": "LOST_STATE",
}

LIFECYCLE_SIGNALS = {
    "REQUESTER_CANCELLED",
    "REQUESTER_DETACHED",
    "TRANSPORT_DISCONNECTED",
    "UI_DISMISSED",
    "WAIT_WINDOW_ELAPSED",
}


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be an object")
    return value


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def base_projection() -> dict[str, Any]:
    return {
        "durable_event_type": None,
        "authority_state": "PENDING",
        "requester_state": "ATTACHED",
        "presentation_state": "VISIBLE",
        "execution_state": "UNUSED",
        "outward_status": "WAITING_FOR_USER",
        "user_message": "Your decision is still pending. Nothing was executed.",
        "execution_blocked": True,
        "execution_claim_allowed": False,
        "resolution": None,
    }


def fail_closed(errors: list[str]) -> dict[str, Any]:
    projection = base_projection()
    projection.update(
        outward_status="ADAPTER_ERROR",
        user_message="Approval state could not be safely projected. Nothing was executed.",
    )
    return {
        "valid": False,
        "errors": errors,
        "projection": projection,
    }


def validate_input(value: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return {}, ["input must be an object"]

    extra = set(value) - INPUT_FIELDS
    require(errors, not extra, f"input contains unsupported fields: {sorted(extra)}")

    approval_id = value.get("approval_id")
    signal = value.get("signal")
    actor = value.get("actor")
    reason = value.get("reason")
    evidence_ref = value.get("evidence_ref")
    exact_bindings_match = value.get("exact_bindings_match")
    expiry_policy_configured = value.get("expiry_policy_configured")

    signal_valid = isinstance(signal, str) and signal in SIGNALS
    require(errors, is_nonempty_string(approval_id), "approval_id is required")
    require(errors, signal_valid, f"unsupported signal: {signal!r}")
    require(errors, is_nonempty_string(reason), "reason is required")
    require(
        errors,
        evidence_ref is None or is_nonempty_string(evidence_ref),
        "evidence_ref must be null or a non-empty string",
    )
    require(errors, type(exact_bindings_match) is bool, "exact_bindings_match must be boolean")
    require(errors, type(expiry_policy_configured) is bool, "expiry_policy_configured must be boolean")

    if not isinstance(actor, dict):
        errors.append("actor must be an object")
        actor_type = None
        actor_id = None
    else:
        extra_actor = set(actor) - {"type", "id"}
        require(errors, not extra_actor, f"actor contains unsupported fields: {sorted(extra_actor)}")
        actor_type = actor.get("type")
        actor_id = actor.get("id")
        require(errors, is_nonempty_string(actor_type), "actor.type is required")
        require(errors, is_nonempty_string(actor_id), "actor.id is required")

    if signal_valid:
        require(
            errors,
            isinstance(actor_type, str) and actor_type in ACTOR_OWNERS[signal],
            f"actor {actor_type!r} cannot emit {signal}",
        )

        if signal in EVIDENCE_REQUIRED:
            require(errors, is_nonempty_string(evidence_ref), f"{signal} requires evidence_ref")

        if signal == "POLICY_EXPIRED":
            require(
                errors,
                expiry_policy_configured is True,
                "POLICY_EXPIRED requires configured expiry policy",
            )

        if signal == "USER_APPROVED":
            require(
                errors,
                exact_bindings_match is True,
                "USER_APPROVED requires exact action and scope bindings",
            )

    return value, errors


def project_signal(value: Any) -> dict[str, Any]:
    signal_input, errors = validate_input(value)
    if errors:
        return fail_closed(errors)

    signal = signal_input["signal"]
    actor = signal_input["actor"]
    projection = base_projection()
    projection["durable_event_type"] = EVENT_TYPES[signal]
    projection["outward_status"] = OUTWARD_STATUS[signal]
    projection["user_message"] = MESSAGES[signal]

    if signal == "USER_APPROVED":
        projection["authority_state"] = "APPROVED"
        projection["execution_blocked"] = False
        projection["execution_claim_allowed"] = True
    elif signal == "USER_REJECTED":
        projection["authority_state"] = "REJECTED"
    elif signal == "REQUESTER_CANCELLED":
        projection["requester_state"] = "CANCELLED"
    elif signal == "REQUESTER_DETACHED":
        projection["requester_state"] = "DETACHED"
    elif signal == "TRANSPORT_DISCONNECTED":
        projection["presentation_state"] = "DISCONNECTED"
    elif signal == "UI_DISMISSED":
        projection["presentation_state"] = "NOT_PRESENTED"
    elif signal == "POLICY_EXPIRED":
        projection["authority_state"] = "EXPIRED"
    elif signal == "CONTEXT_INVALIDATED":
        projection["authority_state"] = "INVALIDATED"
    elif signal == "STATE_LOST":
        projection["authority_state"] = "LOST"

    if signal in {
        "USER_APPROVED",
        "USER_REJECTED",
        "POLICY_EXPIRED",
        "CONTEXT_INVALIDATED",
        "STATE_LOST",
    }:
        projection["resolution"] = {
            "event_type": EVENT_TYPES[signal],
            "actor_type": actor["type"],
            "actor_id": actor["id"],
            "reason": signal_input["reason"],
            "evidence_ref": signal_input.get("evidence_ref"),
        }

    return {
        "valid": True,
        "errors": [],
        "projection": projection,
    }


def unsafe_legacy_status(signal: str) -> str:
    """Illustrate the coarse projection that creates the observed product bug."""
    if signal == "USER_APPROVED":
        return "APPROVED"
    if signal == "USER_REJECTED":
        return "REJECTED"
    return "APPROVAL_NOT_GRANTED"


def validate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if fixture.get("fixture_id") != "review_decision_adapter_cases_v0.1":
        errors.append("fixture: unexpected fixture_id")
    if fixture.get("fixture_version") != "ls-review-decision-adapter-v0.1":
        errors.append("fixture: unexpected fixture_version")

    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        return {
            "fixture_id": fixture.get("fixture_id"),
            "fixture_version": fixture.get("fixture_version"),
            "passed": False,
            "errors": errors + ["fixture: cases must be a non-empty array"],
            "results": [],
            "invariants": {},
        }

    case_ids = [
        case.get("case_id")
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("case_id"), str)
    ]
    case_counts = Counter(case_ids)
    require(
        errors,
        set(case_counts) == REQUIRED_CASES and all(count == 1 for count in case_counts.values()),
        "fixture: required adapter cases must appear exactly once",
    )

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"fixture.cases[{index}]: must be an object")
            continue

        raw_case_id = case.get("case_id")
        case_id = raw_case_id if isinstance(raw_case_id, str) else f"case[{index}]"
        expected = case.get("expected_projection")
        if not isinstance(expected, dict):
            errors.append(f"{case_id}: expected_projection is required")
            continue

        first = project_signal(case.get("input"))
        second = project_signal(deepcopy(case.get("input")))
        if first != second:
            errors.append(f"{case_id}: projection is not deterministic")
        if not first["valid"]:
            errors.extend(f"{case_id}: {error}" for error in first["errors"])
        if first["projection"] != expected:
            errors.append(
                f"{case_id}: projection mismatch: expected {expected}, observed {first['projection']}"
            )

        raw_signal = case.get("input", {}).get("signal") if isinstance(case.get("input"), dict) else None
        signal = raw_signal if isinstance(raw_signal, str) else "<invalid>"
        results.append(
            {
                "case_id": case_id,
                "input_signal": signal,
                "unsafe_legacy_status": unsafe_legacy_status(signal),
                "safe_result": first,
            }
        )

    for result in results:
        if result["input_signal"] not in LIFECYCLE_SIGNALS:
            continue
        projection = result["safe_result"]["projection"]
        require(
            errors,
            projection["authority_state"] == "PENDING",
            f"{result['case_id']}: lifecycle loss must preserve PENDING authority",
        )
        require(
            errors,
            projection["execution_state"] == "UNUSED" and projection["execution_blocked"] is True,
            f"{result['case_id']}: lifecycle loss must keep execution blocked and UNUSED",
        )
        require(
            errors,
            projection["durable_event_type"] != "UserRejected",
            f"{result['case_id']}: lifecycle loss cannot manufacture UserRejected",
        )

    return {
        "fixture_id": fixture.get("fixture_id"),
        "fixture_version": fixture.get("fixture_version"),
        "passed": not errors,
        "errors": errors,
        "results": results,
        "invariants": {
            "adapter_never_invents_user_rejection": all(
                result["safe_result"]["projection"]["durable_event_type"] != "UserRejected"
                for result in results
                if result["input_signal"] in LIFECYCLE_SIGNALS
            ),
            "lifecycle_loss_preserves_pending": all(
                result["safe_result"]["projection"]["authority_state"] == "PENDING"
                for result in results
                if result["input_signal"] in LIFECYCLE_SIGNALS
            ),
            "safe_projection_is_deterministic": not any(
                "not deterministic" in error for error in errors
            ),
        },
    }


def render_demo(report: dict[str, Any]) -> str:
    primary = next(
        result for result in report["results"] if result["case_id"] == "requester_cancelled"
    )
    projection = primary["safe_result"]["projection"]
    return f"""LS ReviewDecision Adapter — 30-second demo

SCENARIO
  The user is still reviewing an action when the requester stops waiting.

COARSE LEGACY PROJECTION
  {primary['unsafe_legacy_status']}
  Problem: requester lifecycle was collapsed into an authority outcome.

LS SAFE PROJECTION
  {projection['user_message']}
  Authority:    {projection['authority_state']}
  Requester:    {projection['requester_state']}
  Presentation: {projection['presentation_state']}
  Execution:    {projection['execution_state']}
  Blocked:      {str(projection['execution_blocked']).lower()}

PRODUCT GUARANTEE
  The adapter did not invent a user decision.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--check", action="store_true", help="print only the fixture pass/fail contract")
    parser.add_argument("--demo", action="store_true", help="render the unsafe-vs-safe product demo")
    args = parser.parse_args()

    report = validate_fixture(load_object(args.fixture))
    if args.check:
        if report["passed"]:
            print("PASS: LS ReviewDecision adapter v0.1")
        else:
            print("FAIL: " + "; ".join(report["errors"]))
    elif args.demo:
        if report["passed"]:
            print(render_demo(report))
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
