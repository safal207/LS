from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.network_health import build_report  # noqa: E402
from scripts.network_health_fix_plan import build_fix_plan  # noqa: E402


def build_operator_actions(report: dict[str, Any], fix_plan: dict[str, Any]) -> dict[str, Any]:
    risks = set(report.get("adequacy_risks") or [])
    weak_routes = list(report.get("weak_routes") or [])
    observer_status = report.get("observer_status")
    top_route = report.get("top_route") or {}
    resonance = report.get("resonance_units") or {}

    env_overrides: dict[str, str] = {}
    config_hints: list[dict[str, str]] = []
    route_actions: list[dict[str, str]] = []

    if "too many weak routes" in risks:
        env_overrides["GRAPH_TRAIL_EXPLORATION_RATE"] = "0.05"
        config_hints.append(
            {
                "target": "graph.trail.exploration_rate",
                "value": "0.05",
                "reason": "reduce exploration noise while weak routes are still being reinforced",
            }
        )

    if "adequacy below tuning fork" in risks:
        env_overrides["GRAPH_DERIVED_MODULE_MIN_QUALITY"] = "0.80"
        env_overrides["GRAPH_DERIVED_MODULE_MIN_TRUST"] = "0.70"
        config_hints.extend(
            [
                {
                    "target": "graph.derived_modules.min_quality",
                    "value": "0.80",
                    "reason": "raise the admission bar until answer adequacy recovers",
                },
                {
                    "target": "graph.derived_modules.min_trust",
                    "value": "0.70",
                    "reason": "do not route through weak derived modules while adequacy is below the tuning fork",
                },
            ]
        )

    if weak_routes:
        route_actions.append(
            {
                "action": "demote_weak_routes",
                "targets": ", ".join(weak_routes),
                "reason": "these routes are currently dragging network quality or goal alignment down",
            }
        )

    if observer_status in {"watch", "intervene"} and top_route.get("route_key"):
        route_actions.append(
            {
                "action": "keep_primary_route",
                "targets": str(top_route.get("route_key")),
                "reason": "keep the strongest current backbone while repairing weak paths around it",
            }
        )

    if int(resonance.get("count", 0) or 0) == 0:
        route_actions.append(
            {
                "action": "seed_resonance_memory",
                "targets": "strong non-reuse cooperative answers",
                "reason": "the network does not yet have reusable reasoning-route memory",
            }
        )

    if observer_status == "intervene":
        env_overrides["GRAPH_CARE_CYCLES_ENABLED"] = "true"
        config_hints.append(
            {
                "target": "graph.care_cycles.enabled",
                "value": "true",
                "reason": "force module review before further promotion under intervene state",
            }
        )

    shell_lines = [f"$env:{key} = \"{value}\"" for key, value in env_overrides.items()]

    return {
        "overall_priority": fix_plan.get("overall_priority"),
        "env_overrides": env_overrides,
        "config_hints": config_hints,
        "route_actions": route_actions,
        "shell": shell_lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest safe operator actions from current network health.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text output.")
    args = parser.parse_args()

    report = build_report()
    fix_plan = build_fix_plan(report)
    actions = build_operator_actions(report, fix_plan)

    if args.json:
        print(
            json.dumps(
                {
                    "report": report,
                    "fix_plan": fix_plan,
                    "operator_actions": actions,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"overall = {actions['overall_priority']}")
    print(
        "env = {value}".format(
            value="; ".join(actions["shell"]) or "<none>"
        )
    )
    print(
        "routes = {value}".format(
            value="; ".join(
                "{action} -> {targets}".format(action=item["action"], targets=item["targets"])
                for item in actions["route_actions"]
            )
            or "<none>"
        )
    )
    print(
        "config = {value}".format(
            value="; ".join(
                "{target}={value}".format(target=item["target"], value=item["value"])
                for item in actions["config_hints"]
            )
            or "<none>"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
