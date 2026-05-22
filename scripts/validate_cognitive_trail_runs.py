#!/usr/bin/env python3
"""Validate LS Cognitive Trail Run artifacts against the JSON schema.

This script is intentionally small and dependency-light. CI installs the single
runtime validation dependency (`jsonschema`) only for this contract check so the
main LS package does not need to carry it as a core dependency.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - exercised only without dependency
    raise SystemExit(
        "Missing dependency: jsonschema. Install it with `python -m pip install jsonschema`."
    ) from exc


DEFAULT_SCHEMA = Path("schemas/cognitive_trail_run.schema.json")
DEFAULT_EXAMPLES_DIR = Path("examples/trails")
EXPECTED_SCHEMA_VERSION = "cognitive_trail_run.v0.1"
FLOAT_TOLERANCE = 1e-9


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def iter_example_files(examples_dir: Path) -> list[Path]:
    if not examples_dir.exists():
        raise FileNotFoundError(f"Examples directory not found: {examples_dir}")

    files = sorted(examples_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON examples found under: {examples_dir}")
    return files


def validate_semantics(path: Path, artifact: dict[str, Any]) -> list[str]:
    """Apply LS-specific checks that JSON Schema cannot express cleanly."""

    errors: list[str] = []

    schema_version = artifact.get("schema_version")
    if schema_version != EXPECTED_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {EXPECTED_SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    result = artifact.get("result", {})
    baseline_reward = result.get("baseline_reward")
    cooperative_reward = result.get("cooperative_reward")
    lift = result.get("lift")
    positive_lift = result.get("positive_lift")

    if all(isinstance(value, (int, float)) for value in (baseline_reward, cooperative_reward, lift)):
        expected_lift = cooperative_reward - baseline_reward
        if not math.isclose(float(lift), float(expected_lift), rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE):
            errors.append(
                f"result.lift must equal cooperative_reward - baseline_reward; "
                f"got {lift}, expected {expected_lift:.12g}"
            )

        expected_positive_lift = expected_lift > 0
        if positive_lift is not expected_positive_lift:
            errors.append(
                f"result.positive_lift must be {expected_positive_lift} for lift {expected_lift:.12g}"
            )

    route = artifact.get("route", [])
    route_steps = [step.get("step") for step in route if isinstance(step, dict)]
    if route_steps != list(range(1, len(route_steps) + 1)):
        errors.append(f"route.step values must be contiguous starting at 1; got {route_steps}")

    route_actors = {step.get("actor") for step in route if isinstance(step, dict)}
    route_roles = {step.get("role") for step in route if isinstance(step, dict)}

    top_actor = result.get("top_actor")
    if top_actor and top_actor not in route_actors:
        errors.append(f"result.top_actor {top_actor!r} is not present in route actors {sorted(route_actors)}")

    top_role = result.get("top_role")
    if top_role and top_role not in route_roles:
        errors.append(f"result.top_role {top_role!r} is not present in route roles {sorted(route_roles)}")

    contribution_summary = artifact.get("contribution_summary", {})
    if contribution_summary.get("top_actor") != top_actor:
        errors.append("contribution_summary.top_actor must match result.top_actor")
    if contribution_summary.get("top_role") != top_role:
        errors.append("contribution_summary.top_role must match result.top_role")

    repeatability = artifact.get("repeatability", {})
    if repeatability.get("should_repeat_route") and not repeatability.get("reason"):
        errors.append("repeatability.reason is required when should_repeat_route is true")

    return [f"{path}: {error}" for error in errors]


def validate_files(schema_path: Path, files: list[Path]) -> int:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    if not files:
        raise FileNotFoundError("No Cognitive Trail Run JSON files were provided for validation")

    failures: list[str] = []
    for path in files:
        if not path.exists():
            failures.append(f"{path}: file not found")
            continue

        artifact = load_json(path)

        schema_errors = sorted(validator.iter_errors(artifact), key=lambda error: list(error.path))
        for error in schema_errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            failures.append(f"{path}: schema error at {location}: {error.message}")

        if isinstance(artifact, dict):
            failures.extend(validate_semantics(path, artifact))
        else:
            failures.append(f"{path}: artifact root must be an object")

    if failures:
        print("Cognitive Trail Run validation failed:\n", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Validated {len(files)} cognitive trail run artifact(s) against {schema_path}.")
    for path in files:
        print(f"- {path}")
    return 0


def validate_examples(schema_path: Path, examples_dir: Path) -> int:
    return validate_files(schema_path, iter_example_files(examples_dir))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Cognitive Trail Run JSON artifacts against the LS schema."
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
        help=f"Path to schema file. Default: {DEFAULT_SCHEMA}",
    )
    parser.add_argument(
        "--examples-dir",
        type=Path,
        default=DEFAULT_EXAMPLES_DIR,
        help=f"Directory containing trail run JSON examples. Default: {DEFAULT_EXAMPLES_DIR}",
    )
    parser.add_argument(
        "--example",
        type=Path,
        action="append",
        default=[],
        help="Specific trail-run JSON file to validate. Can be passed multiple times. If omitted, --examples-dir is used.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.example:
            return validate_files(args.schema, args.example)
        return validate_examples(args.schema, args.examples_dir)
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        print(f"Cognitive Trail Run validation error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
