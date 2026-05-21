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

from graph.path_selector import PathSelector  # noqa: E402
from graph.route_stats import RouteStatsStore  # noqa: E402
from graph.trail_updater import PathExecutionRecord, TrailUpdater  # noqa: E402


def _review_record(
    *,
    route_key: str,
    backend: str,
    quality: dict[str, Any],
    latency_ms: float,
    question_text: str,
) -> PathExecutionRecord:
    return PathExecutionRecord(
        route_key=route_key,
        question_text=question_text,
        graph_mode="pr_review",
        selected_backend=backend,
        quality=quality,
        latency_ms=latency_ms,
    )


def _seed_review_trails(store_path: Path) -> list[dict[str, Any]]:
    store = RouteStatsStore(store_path)
    updater = TrailUpdater(store)
    question = "Review a GitHub pull request for risky state changes, missing tests, and evidence quality."

    records = [
        _review_record(
            route_key="pr_review>local",
            backend="local",
            question_text=question,
            quality={
                "overall": 0.7,
                "relevance": 0.74,
                "thread_relevance": 0.68,
                "coherence": 0.72,
                "goal_alignment_score": 0.67,
                "hallucination_risk": 0.18,
            },
            latency_ms=3600,
        ),
        _review_record(
            route_key="pr_review>local",
            backend="local",
            question_text=question,
            quality={
                "overall": 0.66,
                "relevance": 0.7,
                "thread_relevance": 0.64,
                "coherence": 0.68,
                "goal_alignment_score": 0.62,
                "hallucination_risk": 0.24,
            },
            latency_ms=3400,
        ),
        _review_record(
            route_key="pr_review>local>gonka>mimo",
            backend="cooperative",
            question_text=question,
            quality={
                "overall": 0.9,
                "relevance": 0.92,
                "thread_relevance": 0.89,
                "coherence": 0.91,
                "goal_alignment_score": 0.88,
                "hallucination_risk": 0.07,
            },
            latency_ms=8300,
        ),
        _review_record(
            route_key="pr_review>local>gonka>mimo",
            backend="cooperative",
            question_text=question,
            quality={
                "overall": 0.93,
                "relevance": 0.94,
                "thread_relevance": 0.91,
                "coherence": 0.94,
                "goal_alignment_score": 0.9,
                "hallucination_risk": 0.05,
            },
            latency_ms=7900,
        ),
    ]

    updates = []
    for record in records:
        route, reward = updater.update(record)
        updates.append({"record": record.to_dict(), "reward": reward, "route_stats": route.to_dict()})
    return updates


def build_pr_review_trail_payload(store_path: Path) -> dict[str, Any]:
    updates = _seed_review_trails(store_path)
    store = RouteStatsStore(store_path)
    selector = PathSelector(store, exploration_rate=0.0)
    decision = selector.choose_route(
        graph_mode="pr_review",
        available_backends=["local", "gonka", "mimo"],
        default_backend="local",
        strategy_bias="cooperative_reasoning",
    )
    routes = sorted(
        [route.to_dict() for route in store.list_routes()],
        key=lambda route: (route["pheromone_weight"], route["avg_quality"]),
        reverse=True,
    )
    return {
        "demo": "ls_pr_review_trail_network",
        "task_type": "github_pr_review",
        "use_case": "pick the best learned review route for the next pull request",
        "training_updates": updates,
        "route_map": routes,
        "selected_route": decision.to_dict(),
        "recommended_review_flow": [
            "draft reviewer checks the diff",
            "critic searches for risks and missing tests",
            "verifier checks evidence and continuity",
            "final reviewer emits the human-facing summary",
        ],
        "next_step": "connect this route artifact to a real GitHub PR diff and CI evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LS PR Review Trail Network demo.")
    parser.add_argument("--store-path", type=Path, default=None, help="Optional route stats JSON path.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON artifact output path.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-pr-review-trail-") as tmp:
            payload = build_pr_review_trail_payload(Path(tmp) / "routes.json")
    else:
        payload = build_pr_review_trail_payload(args.store_path)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        decision = payload["selected_route"]
        print("LS PR Review Trail demo")
        print(f"Selected route: {decision['route_key']}")
        print(f"Reason: {decision['reason']}")
        print(f"Pheromone: {decision['pheromone_weight']:.4f}")
        for route in payload["route_map"]:
            print(
                "- {route} runs={runs} pheromone={pheromone:.4f} quality={quality:.2f} latency_ms={latency:.0f}".format(
                    route=route["route_key"],
                    runs=route["runs"],
                    pheromone=route["pheromone_weight"],
                    quality=route["avg_quality"],
                    latency=route["avg_latency_ms"],
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
