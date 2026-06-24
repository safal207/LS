#!/usr/bin/env python3
"""Materialize, validate, and execute Outcome Verification Center fixtures."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from evaluate_outcome_verification import evaluate


def _set_path(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current: Any = target
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = copy.deepcopy(value)
    else:
        current[final] = copy.deepcopy(value)


def materialize(payload: dict[str, Any]) -> list[dict[str, Any]]:
    base_case = payload.get("base_case")
    if base_case is None:
        return payload.get("cases", [payload])

    cases: list[dict[str, Any]] = []
    for definition in payload.get("cases", []):
        case = copy.deepcopy(base_case)
        case["fixture_id"] = definition["fixture_id"]
        case["expected"] = copy.deepcopy(definition.get("expected", {}))
        for path, value in definition.get("overrides", {}).items():
            _set_path(case, path, value)
        cases.append(case)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema", type=Path)
    parser.add_argument("fixtures", type=Path, nargs="+")
    args = parser.parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    validated = 0

    for fixture_path in args.fixtures:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        for case in materialize(payload):
            validated += 1
            schema_errors = sorted(
                validator.iter_errors(case.get("verification")),
                key=lambda error: list(error.absolute_path),
            )
            if schema_errors:
                failures.append(
                    {
                        "fixture_file": str(fixture_path),
                        "fixture_id": case.get("fixture_id", "unknown"),
                        "kind": "schema",
                        "errors": [
                            {
                                "path": ".".join(
                                    str(part) for part in error.absolute_path
                                ),
                                "message": error.message,
                            }
                            for error in schema_errors
                        ],
                    }
                )
                continue

            result = evaluate(case)
            results.append(result)
            expected = case.get("expected", {})
            if (
                result["verdict"] != expected.get("verdict")
                or result["reason_code"] != expected.get("reason_code")
                or result["execution_authorized"] is not False
                or result["retroactive_authorization_created"] is not False
                or result["downstream_learning_gate_required"] is not True
                or result["experience_eligible"]
                is not (result["verdict"] == "VERIFIED")
            ):
                failures.append(
                    {
                        "fixture_file": str(fixture_path),
                        "fixture_id": case.get("fixture_id", "unknown"),
                        "kind": "expected_output",
                        "expected": expected,
                        "actual": {
                            "verdict": result["verdict"],
                            "reason_code": result["reason_code"],
                            "execution_authorized": result["execution_authorized"],
                            "retroactive_authorization_created": result[
                                "retroactive_authorization_created"
                            ],
                            "downstream_learning_gate_required": result[
                                "downstream_learning_gate_required"
                            ],
                            "experience_eligible": result["experience_eligible"],
                        },
                    }
                )

    print(
        json.dumps(
            {
                "validated": validated,
                "results": results,
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
