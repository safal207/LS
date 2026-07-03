#!/usr/bin/env python3
"""Validate one Route Artifact v2 or build a registry projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "modules"))

from route_artifact import RouteArtifactError, build_registry_projection, verify_route_artifact  # noqa: E402


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RouteArtifactError("ROUTE-V2-CLI", f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RouteArtifactError("ROUTE-V2-CLI", f"invalid JSON in {path}: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--artifact", type=Path, help="Route Artifact v2 JSON file")
    group.add_argument(
        "--registry",
        type=Path,
        nargs="+",
        help="Route Artifact files for registry projection",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Local Git checkout used to verify T0 source, origin and exact HEAD",
    )
    parser.add_argument(
        "--allow-t2-audit",
        action="store_true",
        help="Validate a T2 rejection-audit payload without accepting it into the canonical store",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.registry and args.allow_t2_audit:
        parser.error("--allow-t2-audit is only valid with --artifact")

    try:
        if args.artifact:
            result = verify_route_artifact(
                read_json(args.artifact),
                canonical_store=not args.allow_t2_audit,
                repository_root=args.repo_root,
            )
        else:
            result = build_registry_projection(
                [read_json(path) for path in args.registry],
                repository_root=args.repo_root,
            )
    except RouteArtifactError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
