from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from .canonical import CANONICAL_PROFILE, strict_loads
from .witnessed_freshness import PROFILE_ID, verify_witnessed_freshness

FIXTURE_SCHEMA_VERSION = "vtl.witnessed-freshness-fixture/v0.13"


def _set_path(document: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = document
    for part in parts[:-1]:
        cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor[int(last)] = copy.deepcopy(value)
    else:
        cursor[last] = copy.deepcopy(value)


def load_fixture(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    data = strict_loads(raw)
    if not isinstance(data, dict):
        raise ValueError("fixture root must be an object")
    return data


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        authority = copy.deepcopy(fixture["witness_authority"])
        statements = [copy.deepcopy(fixture["statements"][ref]) for ref in case["statement_refs"]]
        for mutation in case.get("authority_mutations", []):
            _set_path(authority, mutation["path"], mutation["value"])
        for mutation in case.get("statement_mutations", []):
            _set_path(statements[mutation["index"]], mutation["path"], mutation["value"])
        result = verify_witnessed_freshness(
            snapshot_view=copy.deepcopy(fixture["snapshot_view"]),
            local_snapshot_valid=case.get("local_snapshot_valid", fixture["local_snapshot_valid"]),
            witness_statements=statements,
            witness_authority=authority,
            now_ms=fixture["base_now_ms"],
        )
        actual = {
            "valid": result.valid,
            "local_snapshot_valid": result.local_snapshot_valid,
            "witness_statement_integrity_valid": result.witness_statement_integrity_valid,
            "witness_signature_valid": result.witness_signature_valid,
            "witness_authority_valid": result.witness_authority_valid,
            "witness_freshness_valid": result.witness_freshness_valid,
            "witness_quorum_valid": result.witness_quorum_valid,
            "view_consistency_valid": result.view_consistency_valid,
            "equivocation_detected": result.equivocation_detected,
            "accepted_witness_ids": list(result.accepted_witness_ids),
            "reason_codes": list(result.reason_codes),
        }
        expected = case["expected"]
        passed = actual["valid"] == expected["valid"] and actual["reason_codes"] == expected["reason_codes"]
        cases.append({"id": case["id"], "actual": actual, "expected": expected, "passed": passed})
    passed = sum(1 for case in cases if case["passed"])
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "cases": cases,
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "all_passed": passed == len(cases),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify VTL v0.13 witnessed freshness vectors")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    result = run_fixture(load_fixture(args.fixture))
    if args.compact:
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
