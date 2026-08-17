from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .canonical import CANONICAL_PROFILE, strict_loads
from .canonical_trust_snapshot import (
    FIXTURE_SCHEMA_VERSION,
    PROFILE_ID,
    verify_canonical_trust_snapshot,
)


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor: Any = document
    for part in parts[:-1]:
        cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor[int(last)] = copy.deepcopy(value)
    else:
        cursor[last] = copy.deepcopy(value)


def _apply_variant(base_snapshot: Mapping[str, Any], variant: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot = copy.deepcopy(dict(base_snapshot))
    if variant:
        for key, value in variant.items():
            snapshot[key] = copy.deepcopy(value)
    return snapshot


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        variant = None
        if case.get("variant_ref") is not None:
            variant = fixture["snapshot_variants"][case["variant_ref"]]
        snapshot = _apply_variant(fixture["base_snapshot"], variant)
        authority = copy.deepcopy(fixture["bootstrap_authority"])
        checkpoint = copy.deepcopy(fixture["checkpoints"][case["checkpoint_ref"]])

        for mutation in case.get("snapshot_mutations", []):
            _set_path(snapshot, mutation["path"], mutation["value"])
        for mutation in case.get("bootstrap_mutations", []):
            _set_path(authority, mutation["path"], mutation["value"])
        for mutation in case.get("checkpoint_mutations", []):
            _set_path(checkpoint, mutation["path"], mutation["value"])

        result = verify_canonical_trust_snapshot(
            snapshot,
            authority,
            checkpoint,
            now_ms=fixture["base_now_ms"],
        )
        actual = {
            "valid": result.valid,
            "snapshot_integrity_valid": result.snapshot_integrity_valid,
            "canonical_profile_valid": result.canonical_profile_valid,
            "bootstrap_signature_valid": result.bootstrap_signature_valid,
            "bootstrap_authority_valid": result.bootstrap_authority_valid,
            "freshness_valid": result.freshness_valid,
            "continuity_valid": result.continuity_valid,
            "reason_codes": list(result.reason_codes),
        }
        results.append(
            {
                "id": case["id"],
                "actual": actual,
                "expected": case["expected"],
                "passed": actual == case["expected"],
            }
        )

    fresh = copy.deepcopy(fixture["base_snapshot"])
    base_result = verify_canonical_trust_snapshot(
        fresh,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    parity = {
        "signed_payload_base64": base_result.signed_payload_base64,
        "signed_payload_matches_expected": (
            base_result.signed_payload_base64
            == fixture["expected_fresh_signed_payload_base64"]
        ),
        "signature_base64": fresh["signature"],
        "signature_matches_expected": (
            fresh["signature"] == fixture["expected_fresh_signature_base64"]
        ),
        "snapshot_digest": base_result.snapshot_digest,
        "snapshot_digest_matches_expected": (
            base_result.snapshot_digest == fixture["expected_fresh_snapshot_digest"]
        ),
    }
    passed = sum(1 for result in results if result["passed"])
    all_passed = (
        passed == len(results)
        and parity["signed_payload_matches_expected"]
        and parity["signature_matches_expected"]
        and parity["snapshot_digest_matches_expected"]
    )
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "parity": parity,
        "cases": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_passed": all_passed,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run VTL v0.12 canonical trust-root snapshot conformance"
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)

    fixture = strict_loads(args.fixture.read_text(encoding="utf-8"))
    result = run_fixture(fixture)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
