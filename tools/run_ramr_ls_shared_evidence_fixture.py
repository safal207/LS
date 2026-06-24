#!/usr/bin/env python3
"""Validate the frozen RAMR-LS recovered-evidence fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "fixtures"
    / "operational-continuity"
    / "shared-envelope"
    / "duplicate_successful_outcome.json"
)
OUTPUT_PATH = ROOT / "artifacts" / "ramr-ls-duplicate-successful-outcome-result.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _validate_top_level(fixture: dict[str, Any]) -> None:
    required = {
        "envelope_version",
        "fixture_id",
        "frozen",
        "synthetic",
        "query_context",
        "authoritative_state",
        "proposed_action",
        "retrieval_variants",
        "cross_layer_invariants",
    }
    missing = sorted(required - fixture.keys())
    if missing:
        raise ValueError(f"Missing top-level fields: {missing}")
    if fixture["envelope_version"] != "ramr-ls-evidence-v0.1":
        raise ValueError("Unsupported envelope version")
    if fixture["fixture_id"] != "duplicate_successful_outcome":
        raise ValueError("Unexpected fixture id")
    if fixture["frozen"] is not True or fixture["synthetic"] is not True:
        raise ValueError("Shared fixture must be frozen and synthetic")


def _completion_recovered(variant: dict[str, Any], action: dict[str, Any]) -> bool:
    for item in variant.get("recovered_evidence", []):
        if item.get("evidence_type") != "completion_record":
            continue
        bindings = item.get("bindings", {})
        if (
            bindings.get("side_effect_key") == action.get("side_effect_key")
            and bindings.get("action_ref") == action.get("action_ref")
            and bindings.get("idempotency_key") == action.get("idempotency_key")
        ):
            return True
    return False


def _authoritative_completion_exists(
    authoritative_state: dict[str, Any], action: dict[str, Any]
) -> bool:
    for completed in authoritative_state.get("completed_side_effects", []):
        if (
            completed.get("side_effect_key") == action.get("side_effect_key")
            and completed.get("action_ref") == action.get("action_ref")
            and completed.get("idempotency_key") == action.get("idempotency_key")
        ):
            return True
    return False


def _bindings_match(fixture: dict[str, Any]) -> bool:
    action = fixture["proposed_action"]
    current = fixture["authoritative_state"]
    return all(
        action.get(name) == current.get(name)
        for name in (
            "workspace_id",
            "continuation_id",
            "intent_digest",
            "target_state_digest",
        )
    )


def evaluate_variant(fixture: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    action = fixture["proposed_action"]
    authoritative_state = fixture["authoritative_state"]

    completion_recovered = _completion_recovered(variant, action)
    ramr_duplicate = not completion_recovered
    observed_ramr = {
        "completion_record_recovered": completion_recovered,
        "naive_duplicate_side_effect": ramr_duplicate,
        "duplicate_side_effect_rate": 1.0 if ramr_duplicate else 0.0,
    }

    failed: list[str] = []
    if not _bindings_match(fixture):
        ls_outcome = "REVALIDATE"
        failed.append("binding_mismatch")
    elif _authoritative_completion_exists(authoritative_state, action):
        ls_outcome = "REJECT"
        failed.append("side_effect_must_not_repeat")
    elif not completion_recovered:
        ls_outcome = "ABSTAIN"
        failed.append("authoritative_completion_state_unavailable")
    else:
        ls_outcome = "RESUME"

    observed_ls = {
        "outcome": ls_outcome,
        "failed_invariants": failed,
        "authority_source": "authoritative_state",
    }

    expected_ramr = variant["expected_ramr"]
    expected_ls = variant["expected_ls"]
    return {
        "variant_id": variant["variant_id"],
        "observed_ramr": observed_ramr,
        "expected_ramr": expected_ramr,
        "observed_ls": observed_ls,
        "expected_ls": expected_ls,
        "passed": observed_ramr == expected_ramr and observed_ls == expected_ls,
    }


def main() -> int:
    fixture = _load_json(FIXTURE_PATH)
    _validate_top_level(fixture)

    results = [evaluate_variant(fixture, variant) for variant in fixture["retrieval_variants"]]
    passed = sum(bool(result["passed"]) for result in results)
    report = {
        "envelope_version": fixture["envelope_version"],
        "fixture_id": fixture["fixture_id"],
        "frozen": fixture["frozen"],
        "variants_total": len(results),
        "variants_passed": passed,
        "cross_layer_property": (
            "RAMR may report retrieval-driven duplicate risk while LS still rejects replay "
            "from authoritative completion state"
        ),
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
