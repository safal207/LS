from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.route_stats import RouteStatsStore  # noqa: E402
from graph.trail_updater import PathExecutionRecord, TrailUpdater, compute_route_reward  # noqa: E402


def _record(
    *,
    route_key: str,
    selected_backend: str,
    quality: dict[str, Any],
    latency_ms: float,
) -> PathExecutionRecord:
    return PathExecutionRecord(
        route_key=route_key,
        question_text="Review a pull request for safety, correctness, and evidence quality.",
        graph_mode="code_review",
        selected_backend=selected_backend,
        quality=quality,
        latency_ms=latency_ms,
    )


def build_demo_payload(store_path: Path) -> dict[str, Any]:
    store = RouteStatsStore(store_path)
    updater = TrailUpdater(store)

    records = [
        _record(
            route_key="code_review>single_model",
            selected_backend="local",
            quality={
                "overall": 0.68,
                "relevance": 0.72,
                "thread_relevance": 0.66,
                "coherence": 0.7,
                "goal_alignment_score": 0.64,
                "hallucination_risk": 0.22,
            },
            latency_ms=4200,
        ),
        _record(
            route_key="code_review>draft>critic>verifier",
            selected_backend="cooperative",
            quality={
                "overall": 0.91,
                "relevance": 0.93,
                "thread_relevance": 0.9,
                "coherence": 0.92,
                "goal_alignment_score": 0.89,
                "hallucination_risk": 0.06,
            },
            latency_ms=7800,
        ),
    ]

    route_results = []
    for record in records:
        saved, reward = updater.update(record)
        route_results.append(
            {
                "record": record.to_dict(),
                "route_reward": reward,
                "route_stats": saved.to_dict(),
            }
        )

    best = max(route_results, key=lambda item: item["route_stats"]["pheromone_weight"])
    return {
        "demo": "ls_cognitive_trail_network",
        "metaphor": "agents leave mountain trails; successful trails become easier to follow",
        "task_type": "code_review",
        "routes": route_results,
        "best_route": best["route_stats"]["route_key"],
        "decision": "prefer_for_next_similar_task",
        "why_it_matters": [
            "the next agent group does not start from zero",
            "good cooperative routes gain weight",
            "weak routes stay visible but lose priority",
            "route choice becomes auditable",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LS Cognitive Trail Network demo.")
    parser.add_argument("--store-path", type=Path, default=None, help="Optional route stats JSON path.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON artifact output path.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-cognitive-trail-") as tmp:
            payload = build_demo_payload(Path(tmp) / "routes.json")
    else:
        payload = build_demo_payload(args.store_path)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("LS Cognitive Trail Network demo")
        print(f"Task type: {payload['task_type']}")
        print(f"Best route: {payload['best_route']}")
        print(f"Decision: {payload['decision']}")
        for route in payload["routes"]:
            stats = route["route_stats"]
            print(
                "- {route} reward={reward:.4f} pheromone={pheromone:.4f} quality={quality:.2f}".format(
                    route=stats["route_key"],
                    reward=route["route_reward"],
                    pheromone=stats["pheromone_weight"],
                    quality=stats["avg_quality"],
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
