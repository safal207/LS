#!/usr/bin/env python3
"""Deterministic trust gate for the LS OpenAI Build Week demo.

The gate consumes normalized, evidence-bearing pull-request state and a
separate trusted policy. It performs no network calls and no delivery action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "build-week" / "policy" / "trust-policy.json"
INPUT_SCHEMA_VERSION = "ls.build_week.trust_input.v0.1"
POLICY_SCHEMA_VERSION = "ls.build_week.trust_policy.v0.1"
REPORT_SCHEMA_VERSION = "ls.build_week.trust_report.v0.1"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
SCENARIO_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
LANE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
CHECK_STATUSES = ("PASS", "FAIL", "NOT_RUN")
MAX_JSON_BYTES = 65536

STATUS_VOCABULARY = {
    "PASS": "The check ran for the required evidence and satisfied policy.",
    "FAIL": "The check ran or evidence was present, but policy was not satisfied.",
    "NOT_RUN": "Required evidence is absent or the required check did not execute.",
}


class TrustInputError(ValueError):
    """Raised when policy or evidence input is malformed."""


def canonical_json(value: Any) -> bytes:
    """Return stable JSON bytes used for deterministic report bindings."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def decision_evidence(value: Any) -> Any:
    """Remove fixture-only oracle data from the evidence digest preimage."""
    if not isinstance(value, dict):
        return value
    evidence = deepcopy(value)
    evidence.pop("expected_outcome", None)
    return evidence


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TrustInputError(f"{location} must be an object")
    return value


def _require_exact_keys(
    value: dict[str, Any],
    required: set[str],
    location: str,
    optional: Optional[set[str]] = None,
) -> None:
    optional = optional or set()
    missing = required - set(value)
    extra = set(value) - required - optional
    if missing:
        raise TrustInputError(f"{location} is missing fields: {sorted(missing)}")
    if extra:
        raise TrustInputError(f"{location} has unsupported fields: {sorted(extra)}")


def _require_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrustInputError(f"{location} must be a non-empty string")
    return value


def _require_sha(value: Any, location: str) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise TrustInputError(f"{location} must be a lowercase 40-character commit SHA")
    return value


def validate_policy(value: Any) -> dict[str, Any]:
    policy = _require_object(value, "policy")
    _require_exact_keys(
        policy,
        {"schema_version", "trusted_reviewers", "required_lanes", "accepted_review_states"},
        "policy",
    )
    if policy["schema_version"] != POLICY_SCHEMA_VERSION:
        raise TrustInputError(f"policy.schema_version must be {POLICY_SCHEMA_VERSION}")

    reviewers = policy["trusted_reviewers"]
    if not isinstance(reviewers, list) or not reviewers:
        raise TrustInputError("policy.trusted_reviewers must be a non-empty array")
    reviewer_keys: set[tuple[str, str, str]] = set()
    for index, reviewer_value in enumerate(reviewers):
        location = f"policy.trusted_reviewers[{index}]"
        reviewer = _require_object(reviewer_value, location)
        _require_exact_keys(reviewer, {"login", "account_type", "evidence_source"}, location)
        login = _require_string(reviewer["login"], f"{location}.login")
        account_type = _require_string(reviewer["account_type"], f"{location}.account_type")
        evidence_source = _require_string(reviewer["evidence_source"], f"{location}.evidence_source")
        key = (login, account_type, evidence_source)
        if key in reviewer_keys:
            raise TrustInputError(f"{location} duplicates a trusted reviewer route")
        reviewer_keys.add(key)

    required_lanes = policy["required_lanes"]
    if not isinstance(required_lanes, list) or not required_lanes:
        raise TrustInputError("policy.required_lanes must be a non-empty array")
    if any(not isinstance(name, str) or not LANE_PATTERN.fullmatch(name) for name in required_lanes):
        raise TrustInputError("policy.required_lanes contains an invalid lane name")
    if len(set(required_lanes)) != len(required_lanes):
        raise TrustInputError("policy.required_lanes must not contain duplicates")

    states = policy["accepted_review_states"]
    if not isinstance(states, list) or not states:
        raise TrustInputError("policy.accepted_review_states must be a non-empty array")
    if any(not isinstance(state, str) or not state for state in states):
        raise TrustInputError("policy.accepted_review_states contains an invalid state")
    if len(set(states)) != len(states):
        raise TrustInputError("policy.accepted_review_states must not contain duplicates")
    return deepcopy(policy)


def validate_input(value: Any) -> dict[str, Any]:
    evidence = _require_object(value, "input")
    _require_exact_keys(
        evidence,
        {"schema_version", "scenario_id", "pull_request", "review", "lanes"},
        "input",
        optional={"expected_outcome"},
    )
    if evidence["schema_version"] != INPUT_SCHEMA_VERSION:
        raise TrustInputError(f"input.schema_version must be {INPUT_SCHEMA_VERSION}")
    if not isinstance(evidence["scenario_id"], str) or not SCENARIO_PATTERN.fullmatch(evidence["scenario_id"]):
        raise TrustInputError("input.scenario_id is invalid")

    pull_request = _require_object(evidence["pull_request"], "input.pull_request")
    _require_exact_keys(pull_request, {"repository", "number", "current_head_sha"}, "input.pull_request")
    repository = pull_request["repository"]
    if not isinstance(repository, str) or not REPOSITORY_PATTERN.fullmatch(repository):
        raise TrustInputError("input.pull_request.repository must match owner/name")
    if type(pull_request["number"]) is not int or pull_request["number"] <= 0:
        raise TrustInputError("input.pull_request.number must be a positive integer")
    _require_sha(pull_request["current_head_sha"], "input.pull_request.current_head_sha")

    review = _require_object(evidence["review"], "input.review")
    _require_exact_keys(review, {"state", "commit_sha", "actor", "provenance"}, "input.review")
    _require_string(review["state"], "input.review.state")
    _require_sha(review["commit_sha"], "input.review.commit_sha")

    actor = _require_object(review["actor"], "input.review.actor")
    _require_exact_keys(actor, {"login", "account_type"}, "input.review.actor")
    _require_string(actor["login"], "input.review.actor.login")
    _require_string(actor["account_type"], "input.review.actor.account_type")

    provenance = _require_object(review["provenance"], "input.review.provenance")
    _require_exact_keys(
        provenance,
        {"source", "authenticated_runtime", "evidence_id"},
        "input.review.provenance",
    )
    _require_string(provenance["source"], "input.review.provenance.source")
    if type(provenance["authenticated_runtime"]) is not bool:
        raise TrustInputError("input.review.provenance.authenticated_runtime must be a boolean")
    _require_string(provenance["evidence_id"], "input.review.provenance.evidence_id")

    lanes = evidence["lanes"]
    if not isinstance(lanes, list):
        raise TrustInputError("input.lanes must be an array")
    lane_names: set[str] = set()
    for index, lane_value in enumerate(lanes):
        location = f"input.lanes[{index}]"
        lane = _require_object(lane_value, location)
        _require_exact_keys(lane, {"name", "status", "head_sha", "evidence_id"}, location)
        name = lane["name"]
        if not isinstance(name, str) or not LANE_PATTERN.fullmatch(name):
            raise TrustInputError(f"{location}.name is invalid")
        if name in lane_names:
            raise TrustInputError(f"{location}.name duplicates lane {name}")
        lane_names.add(name)
        if lane["status"] not in CHECK_STATUSES:
            raise TrustInputError(f"{location}.status must be PASS, FAIL, or NOT_RUN")
        if lane["status"] == "NOT_RUN":
            if lane["head_sha"] is not None or lane["evidence_id"] is not None:
                raise TrustInputError(f"{location} NOT_RUN evidence must not claim a SHA or evidence id")
        else:
            _require_sha(lane["head_sha"], f"{location}.head_sha")
            _require_string(lane["evidence_id"], f"{location}.evidence_id")

    if "expected_outcome" in evidence:
        expected = _require_object(evidence["expected_outcome"], "input.expected_outcome")
        _require_exact_keys(expected, {"verdict", "reason_code"}, "input.expected_outcome")
        if expected["verdict"] not in {"BLOCKED", "TRUSTED"}:
            raise TrustInputError("input.expected_outcome.verdict must be BLOCKED or TRUSTED")
        _require_string(expected["reason_code"], "input.expected_outcome.reason_code")
    return deepcopy(evidence)


def _check(
    check_id: str,
    status: str,
    expected: str,
    observed: str,
    reason_code: Optional[str] = None,
) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise RuntimeError(f"invalid internal check status: {status}")
    return {
        "check_id": check_id,
        "status": status,
        "expected": expected,
        "observed": observed,
        "reason_code": reason_code,
    }


def _invalid_report(value: Any, policy: Any, error: str) -> dict[str, Any]:
    scenario_id = value.get("scenario_id") if isinstance(value, dict) else None
    if not isinstance(scenario_id, str) or not SCENARIO_PATTERN.fullmatch(scenario_id):
        scenario_id = "invalid-input"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "scenario_id": scenario_id,
        "input_digest_sha256": digest(decision_evidence(value)),
        "policy_digest_sha256": digest(policy),
        "verdict": "BLOCKED",
        "trust_state": "UNTRUSTED",
        "delivery_state": "BLOCKED",
        "reason_code": "INVALID_INPUT",
        "headline": "BLOCKED — UNTRUSTED",
        "human_summary": "The trust-gate input is invalid or incomplete.",
        "human_details": [error, "Unknown or malformed evidence cannot authorize delivery."],
        "decision_input": None,
        "checks": [_check("input.valid", "FAIL", "valid policy and evidence", error, "INVALID_INPUT")],
        "status_vocabulary": deepcopy(STATUS_VOCABULARY),
        "human_authorization_required": True,
        "side_effects_performed": False,
    }


def _human_explanation(reason_code: str, evidence: dict[str, Any]) -> tuple[str, list[str]]:
    current_head = evidence["pull_request"]["current_head_sha"]
    review_head = evidence["review"]["commit_sha"]
    if reason_code == "STALE_APPROVAL":
        return (
            f"Approval belongs to {review_head}.",
            [
                f"Current pull-request head is {current_head}.",
                "The approval is stale and cannot authorize delivery.",
            ],
        )
    if reason_code == "REVIEW_NOT_APPROVED":
        return "The observed review state is not an accepted approval.", []
    if reason_code == "UNTRUSTED_REVIEWER":
        actor = evidence["review"]["actor"]
        return (
            "The reviewer identity is not allowed by the trusted policy.",
            [f"Observed reviewer is {actor['login']} with account type {actor['account_type']}."],
        )
    if reason_code == "UNTRUSTED_REVIEW_PROVENANCE":
        return "The approval did not arrive through an authenticated evidence route.", []
    if reason_code == "REQUIRED_LANE_NOT_RUN":
        return "A required delivery lane did not run, so LS failed closed.", []
    if reason_code == "REQUIRED_LANE_FAILED":
        return "A required delivery lane failed, so the decision is blocked.", []
    if reason_code == "STALE_REQUIRED_LANE":
        return "A required lane passed for a different commit SHA and is stale.", []
    return "Evidence did not satisfy the trusted delivery policy.", []


def evaluate(value: Any, policy_value: Any) -> dict[str, Any]:
    """Evaluate evidence against trusted policy and return a deterministic report."""
    try:
        policy = validate_policy(policy_value)
        evidence = validate_input(value)
    except TrustInputError as exc:
        return _invalid_report(value, policy_value, str(exc))

    pull_request = evidence["pull_request"]
    review = evidence["review"]
    actor = review["actor"]
    provenance = review["provenance"]
    current_head = pull_request["current_head_sha"]
    checks: list[dict[str, Any]] = []

    state_passed = review["state"] in policy["accepted_review_states"]
    checks.append(
        _check(
            "review.state",
            "PASS" if state_passed else "FAIL",
            "one of " + ", ".join(policy["accepted_review_states"]),
            review["state"],
            None if state_passed else "REVIEW_NOT_APPROVED",
        )
    )

    matching_routes = [
        reviewer
        for reviewer in policy["trusted_reviewers"]
        if reviewer["login"] == actor["login"] and reviewer["account_type"] == actor["account_type"]
    ]
    identity_passed = bool(matching_routes)
    checks.append(
        _check(
            "review.identity",
            "PASS" if identity_passed else "FAIL",
            "trusted reviewer login and account type",
            f"{actor['login']} ({actor['account_type']})",
            None if identity_passed else "UNTRUSTED_REVIEWER",
        )
    )

    accepted_sources = {route["evidence_source"] for route in matching_routes}
    provenance_passed = provenance["authenticated_runtime"] is True and provenance["source"] in accepted_sources
    checks.append(
        _check(
            "review.provenance",
            "PASS" if provenance_passed else "FAIL",
            "authenticated trusted evidence route",
            f"{provenance['source']} authenticated={str(provenance['authenticated_runtime']).lower()}",
            None if provenance_passed else "UNTRUSTED_REVIEW_PROVENANCE",
        )
    )

    exact_head_passed = review["commit_sha"] == current_head
    checks.append(
        _check(
            "review.exact_head",
            "PASS" if exact_head_passed else "FAIL",
            current_head,
            review["commit_sha"],
            None if exact_head_passed else "STALE_APPROVAL",
        )
    )

    lanes_by_name = {lane["name"]: lane for lane in evidence["lanes"]}
    for lane_name in policy["required_lanes"]:
        lane = lanes_by_name.get(lane_name)
        if lane is None or lane["status"] == "NOT_RUN":
            observed = "MISSING" if lane is None else "NOT_RUN"
            checks.append(
                _check(
                    f"lane.{lane_name}",
                    "NOT_RUN",
                    f"PASS at {current_head}",
                    observed,
                    "REQUIRED_LANE_NOT_RUN",
                )
            )
        elif lane["status"] == "FAIL":
            checks.append(
                _check(
                    f"lane.{lane_name}",
                    "FAIL",
                    f"PASS at {current_head}",
                    f"FAIL at {lane['head_sha']}",
                    "REQUIRED_LANE_FAILED",
                )
            )
        elif lane["head_sha"] != current_head:
            checks.append(
                _check(
                    f"lane.{lane_name}",
                    "FAIL",
                    f"PASS at {current_head}",
                    f"PASS at {lane['head_sha']}",
                    "STALE_REQUIRED_LANE",
                )
            )
        else:
            checks.append(
                _check(
                    f"lane.{lane_name}",
                    "PASS",
                    f"PASS at {current_head}",
                    f"PASS at {lane['head_sha']}",
                )
            )

    blocking_check = next((check for check in checks if check["status"] != "PASS"), None)
    if blocking_check is None:
        verdict = "TRUSTED"
        trust_state = "TRUSTED"
        delivery_state = "ELIGIBLE_FOR_HUMAN_AUTHORIZED_DELIVERY"
        reason_code = "ALL_REQUIRED_EVIDENCE_VALID"
        headline = "TRUSTED — ELIGIBLE FOR HUMAN-AUTHORIZED DELIVERY"
        human_summary = "The approval and every required lane belong to the current pull-request head."
        human_details = [
            f"Exact head verified: {current_head}.",
            "LS did not perform delivery; explicit human authorization is still required.",
        ]
    else:
        verdict = "BLOCKED"
        trust_state = "UNTRUSTED"
        delivery_state = "BLOCKED"
        reason_code = blocking_check["reason_code"] or "POLICY_NOT_SATISFIED"
        headline = "BLOCKED — UNTRUSTED"
        human_summary, human_details = _human_explanation(reason_code, evidence)

    lane_statuses = {lane["name"]: lane["status"] for lane in evidence["lanes"]}
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "scenario_id": evidence["scenario_id"],
        "input_digest_sha256": digest(decision_evidence(evidence)),
        "policy_digest_sha256": digest(policy),
        "verdict": verdict,
        "trust_state": trust_state,
        "delivery_state": delivery_state,
        "reason_code": reason_code,
        "headline": headline,
        "human_summary": human_summary,
        "human_details": human_details,
        "decision_input": {
            "repository": pull_request["repository"],
            "pull_request_number": pull_request["number"],
            "current_head_sha": current_head,
            "review_head_sha": review["commit_sha"],
            "reviewer_login": actor["login"],
            "reviewer_account_type": actor["account_type"],
            "required_lane_statuses": {
                name: lane_statuses.get(name, "NOT_RUN") for name in policy["required_lanes"]
            },
        },
        "checks": checks,
        "status_vocabulary": deepcopy(STATUS_VOCABULARY),
        "human_authorization_required": True,
        "side_effects_performed": False,
    }


def render_human(report: dict[str, Any]) -> str:
    lines = [f"Scenario: {report['scenario_id']}", report["headline"], report["human_summary"]]
    lines.extend(report["human_details"])
    lines.append("Side effects performed: no")
    return "\n".join(lines)


def load_json(path: Path) -> Any:
    raw = path.read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        raise TrustInputError(f"{path} exceeds {MAX_JSON_BYTES} bytes")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustInputError(f"{path} must contain valid UTF-8 JSON") from exc


def _matches_expected(value: Any, report: dict[str, Any]) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("expected_outcome"), dict):
        return False
    expected = value["expected_outcome"]
    return expected.get("verdict") == report["verdict"] and expected.get("reason_code") == report["reason_code"]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate an LS Build Week trust-gate fixture.")
    parser.add_argument("fixture", type=Path, help="Normalized pull-request evidence JSON")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY, help="Trusted policy JSON")
    parser.add_argument("--format", choices=("human", "json", "both"), default="both")
    parser.add_argument("--report-out", type=Path, help="Optional path for the canonical JSON report")
    parser.add_argument(
        "--verify-expected",
        action="store_true",
        help="Fixture mode: exit zero only when verdict and reason match expected_outcome",
    )
    args = parser.parse_args(argv)

    try:
        value = load_json(args.fixture)
        policy = load_json(args.policy)
        report = evaluate(value, policy)
    except (OSError, TrustInputError) as exc:
        print(f"trust-gate input error: {exc}", file=sys.stderr)
        return 2

    report_json = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.report_out is not None:
        args.report_out.write_text(report_json, encoding="utf-8")
    if args.format in {"human", "both"}:
        print(render_human(report))
    if args.format == "both":
        print()
    if args.format in {"json", "both"}:
        print(report_json, end="")

    if args.verify_expected:
        return 0 if _matches_expected(value, report) else 3
    return 0 if report["verdict"] == "TRUSTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
