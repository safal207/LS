#!/usr/bin/env python3
"""Validate one Route Artifact v2 or build a registry projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "modules"))

from route_artifact import (  # noqa: E402
    DEFAULT_PROMOTION_THRESHOLDS_PATH,
    RouteArtifactError,
    build_registry_projection,
    load_promotion_thresholds,
    verify_route_artifact,
)

SCHEMA = ROOT / "schemas" / "route_artifact_v2.schema.json"


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RouteArtifactError(
            "ROUTE-V2-CLI",
            f"file not found: {path}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise RouteArtifactError(
            "ROUTE-V2-CLI",
            f"invalid JSON in {path}: {exc}",
        ) from exc


def validate_schema(value: object) -> None:
    schema = read_json(SCHEMA)
    try:
        jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(item) for item in exc.absolute_path) or "$"
        raise RouteArtifactError(
            "ROUTE-V2-SCHEMA",
            f"{path}: {exc.message}",
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--artifact",
        type=Path,
        help="Route Artifact v2 JSON file",
    )
    group.add_argument(
        "--registry",
        type=Path,
        nargs="+",
        help="Route Artifact files for registry projection",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help=(
            "Local Git checkout used to verify T0 source, "
            "origin and exact HEAD"
        ),
    )
    parser.add_argument(
        "--promotion-thresholds",
        type=Path,
        default=DEFAULT_PROMOTION_THRESHOLDS_PATH,
        help="External numeric promotion-threshold policy JSON",
    )
    parser.add_argument(
        "--allow-t2-audit",
        action="store_true",
        help=(
            "Validate a T2 rejection-audit payload without "
            "accepting it into the canonical store"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.registry and args.allow_t2_audit:
        parser.error(
            "--allow-t2-audit is only valid with --artifact"
        )

    try:
        configured_thresholds = load_promotion_thresholds(
            args.promotion_thresholds
        )
        if args.artifact:
            artifact = read_json(args.artifact)
            validate_schema(artifact)
            result = verify_route_artifact(
                artifact,
                canonical_store=not args.allow_t2_audit,
                repository_root=args.repo_root,
                configured_thresholds=configured_thresholds,
            )
        else:
            artifacts = [read_json(path) for path in args.registry]
            for artifact in artifacts:
                validate_schema(artifact)
            result = build_registry_projection(
                artifacts,
                repository_root=args.repo_root,
                configured_thresholds=configured_thresholds,
            )
    except RouteArtifactError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write(
        json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
