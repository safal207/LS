#!/usr/bin/env python3
"""Deterministic validator for Agent Lifecycle Reliability Conformance v0.1."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "fixtures" / "agent-lifecycle-reliability" / "cases.jsonl"
SCHEMA_PATH = ROOT / "schemas" / "agent_lifecycle_case_v0_1.schema.json"

SCHEMA_VERSION = "ls.agent_lifecycle_case.v0.1"
OPERATIONS = {"ORPHAN_RECONCILE", "CLOSE_AGENT", "STREAM_RECONCILE"}
TERMINAL_REGISTRY_STATES = {"COMPLETED", "ABORTED", "TERMINATED"}
TERMINAL_EVENT_TYPES = {"TURN_COMPLETED", "TURN_INTERRUPTED", "AGENT_TERMINATED"}


class ConformanceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConformanceError(message)


def load_cases() -> list[dict[str, Any]]:
    require(SCHEMA_PATH.exists(), f"missing schema: {SCHEMA_PATH}")
    require(CASES_PATH.exists(), f"missing fixtures: {CASES_PATH}")

    with SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "unexpected JSON Schema dialect")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with CASES_PATH.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ConformanceError(f"invalid JSON on line {line_number}: {exc}") from exc
            validate_shape(case, line_number)
            case_id = case["case_id"]
            require(case_id not in seen_ids, f"duplicate case_id: {case_id}")
            seen_ids.add(case_id)
            cases.append(case)

    require(cases, "fixture suite is empty")
    return cases


def validate_shape(case: dict[str, Any], line_number: int) -> None:
    required = {
        "schema_version",
        "case_id",
        "description",
        "operation",
        "initial",
        "parameters",
        "events",
        "expected",
    }
    require(set(case) == required, f"line {line_number}: unexpected top-level fields")
    require(case["schema_version"] == SCHEMA_VERSION, f"line {line_number}: wrong schema_version")
    require(isinstance(case["case_id"], str) and case["case_id"], f"line {line_number}: invalid case_id")
    require(isinstance(case["description"], str) and case["description"], f"line {line_number}: invalid description")
    require(case["operation"] in OPERATIONS, f"line {line_number}: unsupported operation")

    initial = case["initial"]
    require(set(initial) == {"registry_state", "runtime_state", "active_generation", "client_cursor"}, f"line {line_number}: invalid initial fields")
    require(isinstance(initial["active_generation"], int) and initial["active_generation"] >= 0, f"line {line_number}: invalid active_generation")
    require(isinstance(initial["client_cursor"], int) and initial["client_cursor"] >= 0, f"line {line_number}: invalid client_cursor")

    parameters = case["parameters"]
    require(set(parameters) == {"grace_timeout_ms", "hard_timeout_ms"}, f"line {line_number}: invalid parameter fields")
    for field in ("grace_timeout_ms", "hard_timeout_ms"):
        value = parameters[field]
        require(value is None or (isinstance(value, int) and value >= 0), f"line {line_number}: invalid {field}")

    require(isinstance(case["events"], list), f"line {line_number}: events must be an array")
    for event in case["events"]:
        require(set(event) == {"event_id", "sequence", "generation", "type", "delivery"}, f"line {line_number}: invalid event fields")
        require(isinstance(event["event_id"], str) and event["event_id"], f"line {line_number}: invalid event_id")
        require(isinstance(event["sequence"], int) and event["sequence"] >= 1, f"line {line_number}: invalid sequence")
        require(isinstance(event["generation"], int) and event["generation"] >= 0, f"line {line_number}: invalid generation")
        require(event["delivery"] in {"DELIVERED", "DROPPED", "REPLAYED"}, f"line {line_number}: invalid delivery")

    expected = case["expected"]
    expected_fields = {
        "outcome",
        "reason_code",
        "parent_blocked",
        "slot_released",
        "elapsed_ms",
        "accepted_event_ids",
        "client_cursor",
    }
    require(set(expected) == expected_fields, f"line {line_number}: invalid expected fields")
    require(isinstance(expected["accepted_event_ids"], list), f"line {line_number}: accepted_event_ids must be an array")
    require(len(expected["accepted_event_ids"]) == len(set(expected["accepted_event_ids"])), f"line {line_number}: duplicate expected event ids")


def simulate(case: dict[str, Any]) -> dict[str, Any]:
    operation = case["operation"]
    initial = case["initial"]
    parameters = case["parameters"]

    result: dict[str, Any] = {
        "outcome": "",
        "reason_code": "",
        "parent_blocked": False,
        "slot_released": False,
        "elapsed_ms": 0,
        "accepted_event_ids": [],
        "client_cursor": initial["client_cursor"],
    }

    if operation == "ORPHAN_RECONCILE":
        registry_state = initial["registry_state"]
        runtime_state = initial["runtime_state"]
        if registry_state not in TERMINAL_REGISTRY_STATES | {"MISSING"} and runtime_state == "MISSING":
            result.update(
                outcome="RECONCILED_STALE_REGISTRY",
                reason_code="STALE_REGISTRY_RELEASED",
                slot_released=True,
            )
        elif registry_state == "MISSING" and runtime_state == "RUNNING":
            result.update(
                outcome="ORPHAN_RUNTIME_QUARANTINED",
                reason_code="ORPHAN_RUNTIME_REQUIRES_CONTROL",
                slot_released=False,
            )
        else:
            result.update(outcome="NO_DRIFT", reason_code="REGISTRY_RUNTIME_CONSISTENT")
        return result

    if operation == "CLOSE_AGENT":
        hard_timeout = parameters["hard_timeout_ms"]
        require(hard_timeout is not None, f"{case['case_id']}: CLOSE_AGENT requires hard_timeout_ms")
        if initial["runtime_state"] == "UNRESPONSIVE":
            result.update(
                outcome="FORCE_TERMINATED",
                reason_code="HARD_TIMEOUT_ESCALATION",
                slot_released=True,
                elapsed_ms=hard_timeout,
            )
        elif initial["runtime_state"] == "TERMINATED" or initial["registry_state"] == "TERMINATED":
            result.update(
                outcome="ALREADY_TERMINATED",
                reason_code="IDEMPOTENT_TERMINAL_STATE",
                slot_released=True,
                elapsed_ms=0,
            )
        else:
            grace_timeout = parameters["grace_timeout_ms"] or 0
            result.update(
                outcome="GRACEFULLY_TERMINATED",
                reason_code="GRACEFUL_CLOSE_CONFIRMED",
                slot_released=True,
                elapsed_ms=min(grace_timeout, hard_timeout),
            )
        require(result["elapsed_ms"] <= hard_timeout, f"{case['case_id']}: close exceeded hard timeout")
        return result

    accepted_ids: list[str] = []
    accepted_set: set[str] = set()
    terminal_seen = False
    terminal_replayed = False
    cursor = initial["client_cursor"]
    active_generation = initial["active_generation"]

    for event in case["events"]:
        if event["generation"] != active_generation:
            continue
        if event["delivery"] == "DROPPED":
            continue
        if event["event_id"] in accepted_set:
            continue
        accepted_set.add(event["event_id"])
        accepted_ids.append(event["event_id"])
        cursor = max(cursor, event["sequence"])
        if event["type"] in TERMINAL_EVENT_TYPES:
            terminal_seen = True
            terminal_replayed = terminal_replayed or event["delivery"] == "REPLAYED"

    result["accepted_event_ids"] = accepted_ids
    result["client_cursor"] = cursor
    if terminal_seen:
        result["outcome"] = "COMPLETED_VISIBLE"
        result["reason_code"] = "TERMINAL_EVENT_RECONCILED" if terminal_replayed else "TERMINAL_EVENT_VISIBLE"
    else:
        result["outcome"] = "RECONCILIATION_REQUIRED"
        result["reason_code"] = "TERMINAL_EVENT_NOT_OBSERVED"
    return result


def main() -> int:
    try:
        cases = load_cases()
        results: list[dict[str, Any]] = []
        for case in cases:
            actual = simulate(case)
            expected = case["expected"]
            require(actual == expected, f"{case['case_id']}: expected {expected}, got {actual}")
            require(actual["parent_blocked"] is False, f"{case['case_id']}: parent remained blocked")
            results.append({"case_id": case["case_id"], "status": "PASS", "outcome": actual["outcome"]})

        report = {
            "contract_version": "ls.agent_lifecycle_reliability.v0.1",
            "total": len(results),
            "passed": len(results),
            "failed": 0,
            "cases": results,
            "non_claims": [
                "no Codex integration is claimed",
                "no distributed exactly-once guarantee is claimed",
                "lifecycle recovery does not grant execution authorization",
            ],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (ConformanceError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
