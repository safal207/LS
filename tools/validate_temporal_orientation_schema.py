#!/usr/bin/env python3
"""Validate TOC fixture orientations against the published JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema", type=Path)
    parser.add_argument("fixtures", type=Path, nargs="+")
    args = parser.parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    failures: list[dict[str, object]] = []
    validated = 0

    for fixture_path in args.fixtures:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        for case in payload.get("cases", [payload]):
            validated += 1
            errors = sorted(
                validator.iter_errors(case.get("orientation")),
                key=lambda error: list(error.absolute_path),
            )
            if errors:
                failures.append({
                    "fixture_file": str(fixture_path),
                    "fixture_id": case.get("fixture_id", "unknown"),
                    "errors": [
                        {
                            "path": ".".join(str(part) for part in error.absolute_path),
                            "message": error.message,
                        }
                        for error in errors
                    ],
                })

    print(json.dumps({"validated": validated, "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
