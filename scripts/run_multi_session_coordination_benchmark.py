from __future__ import annotations

import argparse
import json
from pathlib import Path

from ls.coordination_benchmark import (
    RouteProfile,
    apply_pareto_frontier,
    render_markdown_report,
    simulate_route,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "multi-session-coordination"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic multi-session coordination benchmark"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=EXPERIMENT / "generated",
    )
    args = parser.parse_args()

    scenario = _load_json(
        EXPERIMENT / "canonical-five-session-scenario.json"
    )
    profiles = [
        RouteProfile.from_mapping(_load_json(path))
        for path in sorted((EXPERIMENT / "routes").glob("*.json"))
    ]
    runs = apply_pareto_frontier(
        simulate_route(scenario, profile)
        for profile in profiles
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trace_dir = args.output_dir / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    summary = []

    for run in runs:
        route_id = run.result["route_id"]
        result_path = args.output_dir / f"{route_id}.route-result.json"
        result_path.write_text(
            json.dumps(run.result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        trace_path = trace_dir / f"{route_id}.trace.jsonl"
        trace_path.write_text(
            "".join(
                json.dumps(item, sort_keys=True) + "\n"
                for item in run.trace
            ),
            encoding="utf-8",
        )
        summary.append(
            {
                "route_id": route_id,
                "verdict": run.result["verdict"],
                "metrics": run.result["metrics"],
            }
        )

    (args.output_dir / "benchmark-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = render_markdown_report(runs)
    (args.output_dir / "benchmark-report.md").write_text(
        report,
        encoding="utf-8",
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
