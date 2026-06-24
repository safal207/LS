#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.pr_review_mvp import run_trusted_pr_review  # noqa: E402


FIXTURE_ROOT = ROOT / "python/tests/fixtures/trusted-runtime/pr-review"
SCENARIOS = ("allow", "hold", "block")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic LS Trusted PR Review MVP.",
    )
    parser.add_argument(
        "--scenario",
        choices=(*SCENARIOS, "all"),
        default="all",
        help="Scenario to run. Default: all.",
    )
    parser.add_argument(
        "--diff",
        type=Path,
        help="Optional diff path for a single scenario.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build/trusted-pr-review",
        help="Output root. Each scenario receives its own subdirectory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.scenario == "all" and args.diff is not None:
        raise SystemExit("--diff can only be used with one explicit scenario")

    scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
    results = {}
    for scenario in scenarios:
        scenario_root = args.output / scenario
        if scenario_root.exists():
            shutil.rmtree(scenario_root)
        diff_path = args.diff or (FIXTURE_ROOT / f"{scenario}.diff")
        diff_text = diff_path.read_text(encoding="utf-8")
        results[scenario] = run_trusted_pr_review(
            diff_text,
            scenario=scenario,
            output_dir=scenario_root,
        )

    args.output.mkdir(parents=True, exist_ok=True)
    index_path = args.output / "index.json"
    index_path.write_text(
        json.dumps(results, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(results, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
