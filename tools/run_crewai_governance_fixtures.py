#!/usr/bin/env python3
"""Deterministic runner for the LS CrewAI governance conformance profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "crewai-governance"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"

LS_OUTCOMES = {"RESUME", "REVALIDATE", "REJECT", "ABSTAIN"}
CREWAI_DECISIONS = {"allow", "deny", "require_approval", "revise"}
REQUIRED_ACTION_FIELDS = {"tool", "intent_digest", "target_state_digest", "continuation_id"}

OUTCOME_MAPPING: dict[str, dict[str, Any]] = {
    "RESUME": {"status": "EXACT", "decision": "allow", "recommended_decision": "allow"},
    "REVALIDATE": {"status": "EXACT", "decision": "revise", "recommended_decision": "revise"},
    "REJECT": {"status": "EXACT", "decision": "deny", "recommended_decision": "deny"},
    "ABSTAIN": {"status": "UNREPRESENTABLE", "decision": None, "recommended_decision": "defer"},
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _validate_fixture(fixture: dict[str, Any]) -> None:
    required = {
        "fixture_id",
        "description",
        "checkpoint",
        "current_state",
        "proposed_action",
        "expected_ls_outcome",
        "expected_crewai_mapping",
    }
    missing = sorted(required - fixture.keys())
    if missing:
        raise ValueError(f"{fixture.get('fixture_id', '<unknown>')}: missing fields {missing}")

    action = fixture["proposed_action"]
    missing_action = sorted(REQUIRED_ACTION_FIELDS - action.keys())
    if missing_action:
        raise ValueError(f"{fixture['fixture_id']}: missing action fields {missing_action}")

    expected_outcome = fixture["expected_ls_outcome"]
    if expected_outcome not in LS_OUTCOMES:
        raise ValueError(f"{fixture['fixture_id']}: invalid LS outcome {expected_outcome}")

    mapping = fixture["expected_crewai_mapping"]
    if mapping.get("status") not in {"EXACT", "LOSSY", "UNREPRESENTABLE"}:
        raise ValueError(f"{fixture['fixture_id']}: invalid mapping status")
    decision = mapping.get("decision")
    if decision is not None and decision not in CREWAI_DECISIONS:
        raise ValueError(f"{fixture['fixture_id']}: invalid CrewAI decision {decision}")
    if expected_outcome == "ABSTAIN" and decision in {"allow", "require_approval"}:
        raise ValueError(
            f"{fixture['fixture_id']}: ABSTAIN cannot map to {decision}; use an explicit unrepresentable mapping"
        )


def _dependency_chain_complete(fixture: dict[str, Any]) -> bool:
    graph = fixture.get("dependency_graph")
    if not graph:
        return True
    available = {
        node["id"]
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("available") is True and "id" in node
    }
    return all(node_id in available for node_id in graph.get("required_path", []))


def _duplicate_success(fixture: dict[str, Any]) -> bool:
    action = fixture["proposed_action"]
    current = fixture["current_state"]
    action_ref = action.get("action_ref")
    idempotency_key = action.get("idempotency_key")
    return bool(
        action_ref
        and idempotency_key
        and action_ref in set(current.get("completed_action_refs", []))
        and idempotency_key in set(current.get("completed_idempotency_keys", []))
    )


def evaluate(fixture: dict[str, Any]) -> dict[str, Any]:
    _validate_fixture(fixture)
    checkpoint = fixture["checkpoint"]
    current = fixture["current_state"]
    failed: list[str] = []

    approval_id = checkpoint.get("approval_id")
    active_approval_id = current.get("active_approval_id")

    if _duplicate_success(fixture):
        failed.append("successful_action_must_not_repeat")
        outcome = "REJECT"
    elif approval_id is not None and active_approval_id is not None and approval_id != active_approval_id:
        failed.append("approval_must_be_current")
        outcome = "REJECT"
    elif checkpoint.get("intent_digest") != current.get("intent_digest"):
        failed.append("intent_must_match_authorized_intent")
        outcome = "REJECT"
    elif checkpoint.get("continuation_id") != current.get("continuation_id"):
        failed.append("continuation_must_match")
        outcome = "REJECT"
    elif not _dependency_chain_complete(fixture):
        failed.append("required_dependency_chain_incomplete")
        outcome = "ABSTAIN"
    elif checkpoint.get("target_state_digest") != current.get("target_state_digest"):
        failed.append("binding_mismatch:target_state_digest")
        outcome = "REVALIDATE"
    else:
        outcome = "RESUME"

    mapping = OUTCOME_MAPPING[outcome]
    expected_mapping = fixture["expected_crewai_mapping"]
    expected_mapping_core = {
        "status": expected_mapping.get("status"),
        "decision": expected_mapping.get("decision"),
        "recommended_decision": expected_mapping.get("recommended_decision"),
    }
    expected_failed = fixture.get("expected_failed_invariants", [])

    return {
        "fixture_id": fixture["fixture_id"],
        "ls_outcome": outcome,
        "expected_ls_outcome": fixture["expected_ls_outcome"],
        "crewai_mapping": mapping,
        "expected_crewai_mapping": expected_mapping_core,
        "failed_invariants": failed,
        "expected_failed_invariants": expected_failed,
        "passed": (
            outcome == fixture["expected_ls_outcome"]
            and mapping == expected_mapping_core
            and failed == expected_failed
        ),
    }


def _fixture_paths(cli_paths: list[Path]) -> list[Path]:
    if cli_paths:
        return cli_paths
    manifest = _load_json(MANIFEST_PATH)
    return [FIXTURE_DIR / filename for filename in manifest["fixtures"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()

    results = [evaluate(_load_json(path)) for path in _fixture_paths(args.paths)]
    passed = sum(bool(result["passed"]) for result in results)
    report = {
        "profile": "ls-crewai-governance-conformance-v0.1",
        "fixtures_total": len(results),
        "fixtures_passed": passed,
        "pass_rate": passed / len(results) if results else 0.0,
        "unrepresentable_outcomes": sorted(
            {
                result["ls_outcome"]
                for result in results
                if result["crewai_mapping"]["status"] == "UNREPRESENTABLE"
            }
        ),
        "results": results,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
