#!/usr/bin/env python3
"""Seal and score blind review benchmark reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from review_benchmark_adjudication import score, validate_adjudication
from review_benchmark_contract import (
    BenchmarkError,
    TRUE_DECISIONS,
    canonical_bytes,
    load_json,
    seal_report,
    sha256_json,
    validate_case,
    validate_report,
    validate_seal,
    write_json,
)

__all__ = [
    "BenchmarkError",
    "TRUE_DECISIONS",
    "canonical_bytes",
    "load_json",
    "seal_report",
    "score",
    "sha256_json",
    "validate_adjudication",
    "validate_case",
    "validate_report",
    "validate_seal",
    "write_json",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--case", type=Path, required=True)
    seal.add_argument("--report", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    scoring = commands.add_parser("score")
    for name in (
        "case",
        "claude-report",
        "claude-seal",
        "ls-report",
        "ls-seal",
        "adjudication",
        "output",
    ):
        scoring.add_argument(f"--{name}", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        case = load_json(args.case)
        if args.command == "seal":
            write_json(args.output, seal_report(case, load_json(args.report)))
        else:
            reports = {
                "CLAUDE": load_json(args.claude_report),
                "LS": load_json(args.ls_report),
            }
            seals = {
                "CLAUDE": load_json(args.claude_seal),
                "LS": load_json(args.ls_seal),
            }
            write_json(
                args.output,
                score(case, reports, seals, load_json(args.adjudication)),
            )
    except BenchmarkError as exc:
        print(f"review benchmark error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
