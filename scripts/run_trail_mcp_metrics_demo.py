from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for path in (PYTHON_ROOT, MODULES_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from ls.agent_shell.trail_network import METRIC_VERSION, TrailNetworkBridge  # noqa: E402


GOOD_ROUTE = {
    "route_key": "pr_review>local>gonka>mimo",
    "task_id": "demo-good",
    "task_text": "Review a pull request with draft, critic, and verifier roles.",
    "evidence_coverage": 0.9,
    "false_positive_rate": 0.05,
    "human_accepted": True,
    "ci_passed": True,
    "useful_findings": 3,
    "unsupported_claims": 0,
    "latency_ms": 1200,
}

WEAK_ROUTE = {
    "route_key": "pr_review>local",
    "task_id": "demo-weak",
    "task_text": "Review a pull request with one local pass only.",
    "evidence_coverage": 0.25,
    "false_positive_rate": 0.7,
    "human_accepted": False,
    "ci_passed": False,
    "useful_findings": 1,
    "unsupported_claims": 3,
    "latency_ms": 9000,
}


def build_demo_payload(route_store_path: Path, event_log_path: Path) -> dict[str, Any]:
    bridge = TrailNetworkBridge(route_store_path=route_store_path, event_log_path=event_log_path)

    good = bridge.record_outcome(GOOD_ROUTE)
    weak = bridge.record_outcome(WEAK_ROUTE)
    ranking = bridge.query_best_trails({"route_prefix": "pr_review", "limit": 5})["routes"]

    return {
        "demo": "ls_trail_mcp_metrics",
        "metric_version": METRIC_VERSION,
        "plain_ru": [
            "Успех засчитывается только после доказательств, низкого шума и подтверждения человеком или CI.",
            "Слабый совет может получить небольшой reward, но не становится проверенным вкладом.",
            "Рейтинг показывает, какой маршрут стоит пробовать первым в похожей задаче.",
        ],
        "routes": [
            {
                "label": "cooperative_route",
                "route_key": good["route_stats"]["route_key"],
                "reward": good["reward"],
                "outcome_success": good["outcome_success"],
                "decision": good["decision"],
                "success_rate": good["route_stats"]["success_rate"],
                "repeatability_score": good["route_stats"]["repeatability_score"],
                "route_health": good["route_stats"]["route_health"],
            },
            {
                "label": "single_route",
                "route_key": weak["route_stats"]["route_key"],
                "reward": weak["reward"],
                "outcome_success": weak["outcome_success"],
                "decision": weak["decision"],
                "success_rate": weak["route_stats"]["success_rate"],
                "repeatability_score": weak["route_stats"]["repeatability_score"],
                "route_health": weak["route_stats"]["route_health"],
            },
        ],
        "ranking": ranking,
    }


def _print_text(payload: dict[str, Any]) -> None:
    print("LS Trail MCP metrics demo")
    print(f"Metric version: {payload['metric_version']}")
    print("Meaning: сеть запоминает проверенные маршруты, а не просто красивые ответы.")
    print()
    for route in payload["routes"]:
        print(
            "{label}: route={route_key} reward={reward:.4f} success={success} "
            "decision={decision} repeatability={repeatability:.4f} health={health}".format(
                label=route["label"],
                route_key=route["route_key"],
                reward=route["reward"],
                success=str(route["outcome_success"]).lower(),
                decision=route["decision"],
                repeatability=route["repeatability_score"],
                health=route["route_health"],
            )
        )
    print()
    print("Ranking:")
    for index, route in enumerate(payload["ranking"], start=1):
        print(
            "{index}. {route} repeatability={repeatability:.4f} "
            "success_rate={success_rate:.2f} health={health}".format(
                index=index,
                route=route["route_key"],
                repeatability=route["repeatability_score"],
                success_rate=route["success_rate"],
                health=route["route_health"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic LS Trail MCP metrics demo.")
    parser.add_argument("--store-path", type=Path, default=None, help="Optional route stats JSON path.")
    parser.add_argument("--events-path", type=Path, default=None, help="Optional trail event JSONL path.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-trail-mcp-metrics-") as tmp:
            tmp_path = Path(tmp)
            payload = build_demo_payload(
                tmp_path / "routes.json",
                args.events_path or tmp_path / "trail_events.jsonl",
            )
    else:
        payload = build_demo_payload(
            args.store_path,
            args.events_path or args.store_path.with_name("trail_events.jsonl"),
        )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
