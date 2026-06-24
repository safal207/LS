#!/usr/bin/env python3
"""Verify and evaluate the RAMR-canonical shared evidence fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "operational-continuity" / "shared-envelope"
FIXTURE_PATH = FIXTURE_DIR / "duplicate_successful_outcome.json"
DIGEST_PATH = FIXTURE_DIR / "duplicate_successful_outcome.sha256"
OUTPUT_PATH = ROOT / "artifacts" / "ramr-ls-duplicate-successful-outcome-result.json"
CANONICAL_REPOSITORY = "DanceNitra/ramr"
CANONICAL_COMMIT = "8f21771f7ee6012d6839b8c89ceae61f639e93ed"
CANONICAL_PATH = "fixtures/ramr_ls/duplicate_successful_outcome.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _expected_digest() -> str:
    line = DIGEST_PATH.read_text(encoding="utf-8").strip()
    digest_token, filename = line.split(maxsplit=1)
    if filename.strip() != FIXTURE_PATH.name:
        raise ValueError(f"Digest file targets unexpected fixture: {filename}")
    algorithm, digest = digest_token.split(":", maxsplit=1)
    if algorithm != "sha256" or len(digest) != 64:
        raise ValueError("Pinned fixture digest must be sha256:<64 lowercase hex characters>")
    return digest


def _actual_digest() -> str:
    return hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()


def _validate_top_level(fixture: dict[str, Any]) -> None:
    required = {
        "_meta",
        "fixture_id",
        "envelope_version",
        "description",
        "authoritative_state",
        "query_context",
        "cases",
        "scoring",
    }
    missing = sorted(required - fixture.keys())
    if missing:
        raise ValueError(f"Missing top-level fields: {missing}")
    if fixture["fixture_id"] != "duplicate_successful_outcome":
        raise ValueError("Unexpected fixture id")
    if fixture["envelope_version"] != "ramr-ls-evidence-v0.1":
        raise ValueError("Unsupported envelope version")
    if fixture.get("_meta", {}).get("envelope_version") != fixture["envelope_version"]:
        raise ValueError("Metadata and fixture envelope versions differ")
    case_names = [case.get("case") for case in fixture["cases"]]
    if case_names != ["completion_recovered", "completion_not_recovered"]:
        raise ValueError(f"Unexpected canonical case order: {case_names}")


def _binding_matches_context(bindings: dict[str, Any], context: dict[str, Any]) -> bool:
    return all(
        bindings.get(field) == context.get(field)
        for field in ("continuation_id", "intent_digest", "target_state_digest")
    )


def _recovered_side_effect(case: dict[str, Any], fixture: dict[str, Any]) -> bool:
    context = fixture["query_context"]
    ledger = fixture["authoritative_state"].get("completion_ledger", [])
    completed_keys = {
        record.get("side_effect_key")
        for record in ledger
        if record.get("status") == "completed" and _binding_matches_context(record, context)
    }
    for evidence in case.get("recovered_evidence", []):
        if evidence.get("evidence_type") != "completion_record":
            continue
        bindings = evidence.get("bindings", {})
        scope = evidence.get("scope", {})
        if scope.get("workspace_id") != context.get("workspace_id"):
            continue
        if not _binding_matches_context(bindings, context):
            continue
        if bindings.get("side_effect_key") in completed_keys:
            return True
    return False


def _ls_verdict(fixture: dict[str, Any]) -> tuple[str, list[str]]:
    context = fixture["query_context"]
    ledger = fixture["authoritative_state"].get("completion_ledger", [])
    for record in ledger:
        if record.get("status") != "completed":
            continue
        if _binding_matches_context(record, context):
            return "REJECT", ["side_effect_must_not_repeat"]
    return "ABSTAIN", ["authoritative_completion_state_unavailable"]


def evaluate_case(fixture: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    observed_ramr = _recovered_side_effect(case, fixture)
    observed_ls, failed_invariants = _ls_verdict(fixture)
    expected = case["expected"]
    return {
        "case": case["case"],
        "observed": {
            "ramr_recovered_side_effect": observed_ramr,
            "ls_verdict": observed_ls,
            "failed_invariants": failed_invariants,
            "authority_source": "authoritative_state.completion_ledger",
        },
        "expected": expected,
        "passed": (
            observed_ramr == expected["ramr_recovered_side_effect"]
            and observed_ls == expected["ls_verdict"]
        ),
    }


def main() -> int:
    expected_digest = _expected_digest()
    actual_digest = _actual_digest()
    if actual_digest != expected_digest:
        raise ValueError(
            "RAMR canonical fixture digest mismatch: "
            f"expected {expected_digest}, observed {actual_digest}"
        )

    fixture = _load_json(FIXTURE_PATH)
    _validate_top_level(fixture)
    results = [evaluate_case(fixture, case) for case in fixture["cases"]]
    passed = sum(bool(result["passed"]) for result in results)

    report = {
        "profile": "ls-ramr-operational-continuity-interop-v0.1",
        "envelope_version": fixture["envelope_version"],
        "fixture_id": fixture["fixture_id"],
        "canonical_source": {
            "repository": CANONICAL_REPOSITORY,
            "commit": CANONICAL_COMMIT,
            "path": CANONICAL_PATH,
            "sha256": actual_digest,
            "local_mirror_verified": True,
        },
        "cases_total": len(results),
        "cases_passed": passed,
        "boundary_invariant": fixture["scoring"]["boundary_invariant"],
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
