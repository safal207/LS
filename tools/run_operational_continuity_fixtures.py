#!/usr/bin/env python3
"""Deterministic reference runner for LS operational-continuity fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

OUTCOMES = {"RESUME", "REVALIDATE", "REJECT", "ABSTAIN"}


def _binding_mismatches(fixture: dict[str, Any]) -> list[str]:
    checkpoint = fixture.get("checkpoint", {})
    current = fixture.get("current_state", {})
    mismatches: list[str] = []
    for binding in fixture.get("required_bindings", []):
        if checkpoint.get(binding) != current.get(binding):
            mismatches.append(binding)
    return mismatches


def evaluate(fixture: dict[str, Any]) -> dict[str, Any]:
    fixture_id = fixture["fixture_id"]
    checkpoint = fixture.get("checkpoint", {})
    current = fixture.get("current_state", {})
    action = fixture.get("proposed_action", {})
    failed: list[str] = []

    if fixture_id == "resume_no_duplicate_side_effect":
        completed = set(current.get("completed_side_effect_keys", []))
        key = action.get("side_effect_key")
        if key and key in completed:
            failed.append("side_effect_must_not_repeat")
            outcome = "REJECT"
        else:
            outcome = "RESUME"

    elif fixture_id == "superseded_approval_rejected":
        approval_id = checkpoint.get("approval_id")
        active_approval_id = current.get("active_approval_id")
        if approval_id != active_approval_id:
            failed.append("approval_must_be_current")
            outcome = "REJECT"
        else:
            outcome = "RESUME"

    elif fixture_id == "complete_chain_preferred_over_disconnected_facts":
        graph = fixture.get("dependency_graph", {})
        required_path = graph.get("required_path", [])
        available_nodes = {node["id"] for node in graph.get("nodes", []) if node.get("available")}
        if all(node_id in available_nodes for node_id in required_path):
            outcome = "RESUME"
        else:
            failed.append("required_dependency_chain_incomplete")
            outcome = "ABSTAIN"

    elif fixture_id == "workspace_drift_requires_revalidation":
        mismatches = _binding_mismatches(fixture)
        if mismatches:
            failed.extend(f"binding_mismatch:{name}" for name in mismatches)
            outcome = "REVALIDATE"
        else:
            outcome = "RESUME"

    else:
        failed.append("unknown_fixture")
        outcome = "ABSTAIN"

    if outcome not in OUTCOMES:
        raise RuntimeError(f"Invalid outcome: {outcome}")

    return {
        "fixture_id": fixture_id,
        "outcome": outcome,
        "expected_outcome": fixture.get("expected_outcome"),
        "passed": outcome == fixture.get("expected_outcome"),
        "failed_invariants": failed,
        "observed_bindings": {
            name: {
                "checkpoint": checkpoint.get(name),
                "current": current.get(name),
            }
            for name in fixture.get("required_bindings", [])
        },
        "proposed_action": action,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    results = []
    for path in args.paths:
        with path.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)
        results.append(evaluate(fixture))

    print(json.dumps({"results": results}, indent=2, sort_keys=True))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
