#!/usr/bin/env python3
"""Run Personal Cognitive Garden red-team scenarios.

This dependency-free runner turns the reviewer-facing anti-surveillance
boundary into an executable artifact. It is intentionally small and explicit:
requests for private cognitive-garden fields from third parties are blocked
unless the fixture carries explicit subject consent and only asks for
shareable fields.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = REPO_ROOT / "examples" / "personal_cognitive_garden" / "red_team_employer_surveillance_request.json"


PRIVATE_GRAPH_REASONS = {
    "private_graph_access_request": "PRIVATE_GRAPH_ACCESS_REQUEST",
}


class RedTeamInputError(ValueError):
    """Raised when a red-team fixture is malformed."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError as exc:
        raise RedTeamInputError(f"Missing red-team fixture: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RedTeamInputError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RedTeamInputError(f"Expected object at top level in {path}")
    return payload


def as_string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def evaluate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    request = scenario.get("request") or {}
    policy = scenario.get("policy") or {}
    requester = scenario.get("requester") or {}
    scenario_type = str(scenario.get("scenario_type") or "unknown")

    requested_fields = as_string_set(request.get("requested_fields"))
    blocked_fields = as_string_set(policy.get("blocked_fields_by_default"))
    blocked_requested_fields = sorted(requested_fields & blocked_fields)
    explicit_consent = bool(request.get("explicit_subject_consent"))
    requester_type = str(requester.get("type") or "unknown")

    is_third_party = requester_type not in {"self", "human_owner", "owner"}
    asks_private_graph = scenario_type in PRIVATE_GRAPH_REASONS or bool(blocked_requested_fields)

    if is_third_party and asks_private_graph and not explicit_consent:
        decision = "BLOCK"
        reason = PRIVATE_GRAPH_REASONS.get(scenario_type, "PRIVATE_FIELD_ACCESS_REQUEST")
        external_action_allowed = False
        shareable_fields: list[str] = []
    elif explicit_consent and not blocked_requested_fields:
        decision = "LIMITED_CONSENTED_EXPORT"
        reason = "EXPLICIT_CONSENT_WITH_NON_SENSITIVE_FIELDS"
        external_action_allowed = True
        shareable_fields = sorted(requested_fields)
    else:
        decision = "HUMAN_REVIEW"
        reason = "CONSENT_OR_FIELD_SCOPE_REQUIRES_REVIEW"
        external_action_allowed = False
        shareable_fields = []

    return {
        "scenario_id": scenario.get("scenario_id", "unknown"),
        "decision": decision,
        "reason": reason,
        "requester_type": requester_type,
        "explicit_subject_consent": explicit_consent,
        "blocked_requested_fields": blocked_requested_fields,
        "shareable_fields": shareable_fields,
        "external_action_allowed": external_action_allowed,
        "safe_alternative": policy.get("safe_alternative", "aggregate, consented, non-sensitive skill signal"),
        "invariant": policy.get(
            "invariant",
            "The person owns the cognitive garden. External systems may only receive explicitly consented, evidence-backed, non-sensitive views.",
        ),
    }


def assert_expected(result: dict[str, Any], scenario: dict[str, Any]) -> None:
    expected = scenario.get("expected") or {}
    mismatches = []
    for key in ["decision", "reason", "external_action_allowed"]:
        if key in expected and result.get(key) != expected.get(key):
            mismatches.append(f"{key}: expected {expected.get(key)!r}, got {result.get(key)!r}")
    if mismatches:
        raise RedTeamInputError("Red-team expectation mismatch: " + "; ".join(mismatches))


def print_human(result: dict[str, Any]) -> None:
    print("Personal Cognitive Garden red-team")
    print("=" * 34)
    print()
    print(f"Scenario: {result['scenario_id']}")
    print(f"Decision: {result['decision']}")
    print(f"Reason: {result['reason']}")
    print(f"External action allowed: {result['external_action_allowed']}")
    print()
    print("Blocked requested fields:")
    for field in result["blocked_requested_fields"]:
        print(f"  - {field}")
    if not result["blocked_requested_fields"]:
        print("  - none")
    print()
    print(f"Safe alternative: {result['safe_alternative']}")
    print(f"Invariant: {result['invariant']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Personal Cognitive Garden anti-surveillance red-team fixture.")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO, help="Path to a red-team scenario JSON file.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        scenario = load_json(args.scenario.resolve())
        result = evaluate_scenario(scenario)
        assert_expected(result, scenario)
    except RedTeamInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
