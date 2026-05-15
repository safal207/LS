#!/usr/bin/env python3
"""Run the Personal Cognitive Garden anti-surveillance red-team suite.

This runner executes multiple adversarial sharing/export scenarios against the
same small governance evaluator used by `run_pcg_red_team.py`. It is deliberately
explicit and dependency-free so a grant reviewer can reproduce the boundary
without a backend service.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.run_pcg_red_team import RedTeamInputError, assert_expected, evaluate_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = REPO_ROOT / "examples" / "personal_cognitive_garden" / "red_team_suite.json"


def load_suite(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError as exc:
        raise RedTeamInputError(f"Missing red-team suite fixture: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RedTeamInputError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise RedTeamInputError(f"Expected top-level list in {path}")
    for item in payload:
        if not isinstance(item, dict):
            raise RedTeamInputError("Each red-team suite scenario must be an object")
    return payload


def evaluate_suite(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    passed = 0
    counts: dict[str, int] = {}

    for scenario in scenarios:
        result = evaluate_scenario(scenario)
        try:
            assert_expected(result, scenario)
            scenario_passed = True
            passed += 1
        except RedTeamInputError:
            scenario_passed = False
        decision = str(result.get("decision", "unknown"))
        counts[decision] = counts.get(decision, 0) + 1
        rows.append(
            {
                "scenario_id": result.get("scenario_id", "unknown"),
                "decision": decision,
                "reason": result.get("reason", "unknown"),
                "external_action_allowed": result.get("external_action_allowed", False),
                "blocked_requested_fields": result.get("blocked_requested_fields", []),
                "passed": scenario_passed,
            }
        )

    total = len(rows)
    return {
        "total_scenarios": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": 0.0 if total == 0 else round(passed / total, 4),
        "decision_counts": counts,
        "rows": rows,
        "invariant": "The person owns the cognitive garden. External systems may only receive explicitly consented, evidence-backed, non-sensitive views.",
    }


def print_human(report: dict[str, Any]) -> None:
    print("Personal Cognitive Garden red-team suite")
    print("=" * 42)
    print()
    print(f"Total scenarios: {report['total_scenarios']}")
    print(f"Passed: {report['passed']}")
    print(f"Failed: {report['failed']}")
    print(f"Pass rate: {report['pass_rate']}")
    print()
    print("Decision counts:")
    for decision, count in sorted(report["decision_counts"].items()):
        print(f"  - {decision}: {count}")
    print()
    print("Rows:")
    for row in report["rows"]:
        status = "ok" if row["passed"] else "check"
        print(f"  - {row['scenario_id']}: {row['decision']} / {row['reason']} [{status}]")
    print()
    print(f"Invariant: {report['invariant']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Personal Cognitive Garden red-team suite.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE, help="Path to red_team_suite.json.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--min-pass-rate", type=float, default=1.0, help="Fail if pass rate is below this threshold.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        scenarios = load_suite(args.suite.resolve())
        report = evaluate_suite(scenarios)
    except RedTeamInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)

    if float(report["pass_rate"]) < args.min_pass_rate:
        print(
            f"error: pass rate {report['pass_rate']} is below threshold {args.min_pass_rate}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
