from __future__ import annotations

import argparse
import base64
import copy
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .canonical import CANONICAL_PROFILE, canonical_bytes, strict_loads
from .transparency_log import (
    FIXTURE_SCHEMA_VERSION,
    PROFILE_ID,
    checkpoint_digest,
    merkle_leaf_hash,
    signed_checkpoint_payload,
    verify_transparency_log,
)


def _set_path(root: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    current = root
    for part in parts[:-1]:
        current = current[int(part)] if part.isdigit() else current[part]
    last = parts[-1]
    if last.isdigit():
        current[int(last)] = value
    else:
        current[last] = value


def _case_bundle(fixture: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    bundle = copy.deepcopy(fixture["base_bundle"])
    checkpoint_ref = case.get("checkpoint_ref")
    if checkpoint_ref is not None:
        bundle["checkpoint"] = copy.deepcopy(fixture["checkpoint_variants"][checkpoint_ref])
    verifier_ref = case.get("verifier_checkpoint_ref")
    if verifier_ref is not None:
        bundle["verifier_checkpoint"] = copy.deepcopy(
            fixture["verifier_checkpoint_variants"][verifier_ref]
        )
    inclusion_ref = case.get("inclusion_path_ref")
    if inclusion_ref is not None:
        bundle["inclusion_path"] = copy.deepcopy(
            fixture["inclusion_path_variants"][inclusion_ref]
        )
    consistency_ref = case.get("consistency_path_ref")
    if consistency_ref is not None:
        bundle["consistency_path"] = copy.deepcopy(
            fixture["consistency_path_variants"][consistency_ref]
        )
    peer_refs = case.get("peer_checkpoint_refs")
    if peer_refs is not None:
        bundle["peer_checkpoints"] = [
            copy.deepcopy(fixture["checkpoint_variants"][ref]) for ref in peer_refs
        ]
    for mutation in case.get("mutations", []):
        _set_path(bundle, mutation["path"], copy.deepcopy(mutation["value"]))
    return bundle


def _result_dict(result: Any) -> dict[str, Any]:
    value = asdict(result)
    value["reason_codes"] = list(value["reason_codes"])
    return value


def _matches_expected(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def run_fixture(fixture: Any) -> dict[str, Any]:
    if not isinstance(fixture, dict):
        raise ValueError("FIXTURE_ROOT_INVALID")
    if fixture.get("profile_id") != PROFILE_ID:
        raise ValueError("PROFILE_ID_MISMATCH")
    if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise ValueError("SCHEMA_VERSION_MISMATCH")
    if fixture.get("canonical_profile") != CANONICAL_PROFILE:
        raise ValueError("CANONICAL_PROFILE_MISMATCH")

    now_ms = fixture["base_now_ms"]
    cases: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        bundle = _case_bundle(fixture, case)
        actual = _result_dict(verify_transparency_log(bundle, now_ms=now_ms))
        expected = case["expected"]
        cases.append(
            {
                "id": case["id"],
                "actual": actual,
                "expected": expected,
                "passed": _matches_expected(actual, expected),
            }
        )

    base = fixture["base_bundle"]
    entry_bytes = canonical_bytes(base["entry"])
    checkpoint_payload = signed_checkpoint_payload(base["checkpoint"])
    parity = {
        "entry_canonical_base64": base64.b64encode(entry_bytes).decode("ascii"),
        "entry_canonical_matches_expected": (
            base64.b64encode(entry_bytes).decode("ascii")
            == fixture["expected_base_entry_canonical_base64"]
        ),
        "leaf_hash": merkle_leaf_hash(base["entry"]),
        "leaf_hash_matches_expected": (
            merkle_leaf_hash(base["entry"]) == fixture["expected_base_leaf_hash"]
        ),
        "checkpoint_signed_payload_base64": base64.b64encode(checkpoint_payload).decode(
            "ascii"
        ),
        "checkpoint_signed_payload_matches_expected": (
            base64.b64encode(checkpoint_payload).decode("ascii")
            == fixture["expected_base_checkpoint_signed_payload_base64"]
        ),
        "checkpoint_signature_matches_expected": (
            base["checkpoint"]["signature"]
            == fixture["expected_base_checkpoint_signature_base64"]
        ),
        "checkpoint_digest": checkpoint_digest(base["checkpoint"]),
        "checkpoint_digest_matches_expected": (
            checkpoint_digest(base["checkpoint"])
            == fixture["expected_base_checkpoint_digest"]
        ),
        "root_hash_matches_expected": (
            base["checkpoint"]["root_hash"] == fixture["expected_base_root_hash"]
        ),
    }

    passed = sum(1 for case in cases if case["passed"])
    parity_passed = all(
        value for key, value in parity.items() if key.endswith("_matches_expected")
    )
    summary = {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "all_passed": passed == len(cases) and parity_passed,
    }
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "cases": cases,
        "parity": parity,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify VTL v0.14 transparency-log proof vectors"
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)

    fixture = strict_loads(args.fixture.read_text(encoding="utf-8"))
    result = run_fixture(fixture)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
