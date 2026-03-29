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


def _priority(label: str, reason: str, action: str) -> dict[str, str]:
    return {"label": label, "reason": reason, "action": action}


def build_fix_plan(report: dict[str, Any]) -> dict[str, Any]:
    risks = list(report.get("adequacy_risks") or [])
    weak_routes = list(report.get("weak_routes") or [])
    strong_routes = list(report.get("strong_routes") or [])
    strong_coalitions = list(report.get("strong_coalitions") or [])
    stale_modules = list(report.get("stale_modules") or [])
    top_route = report.get("top_route") or {}
    top_module = report.get("top_derived_module") or {}
    resonance = report.get("resonance_units") or {}
    observer_status = report.get("observer_status")

    do_now: list[dict[str, str]] = []
    do_next: list[dict[str, str]] = []
    keep: list[dict[str, str]] = []

    if "adequacy below tuning fork" in risks:
        do_now.append(
            _priority(
                "raise-adequacy",
                "observer says adequacy is below the tuning fork",
                "tighten prompts and route preference toward grounded cooperative answers before raising trust",
            )
        )
    if "too many weak routes" in risks or weak_routes:
        do_now.append(
            _priority(
                "prune-weak-routes",
                "weak routes are still being reinforced",
                "demote weak routes in path selection and stop rewarding them until quality recovers",
            )
        )
    if observer_status == "watch" and not strong_coalitions:
        do_now.append(
            _priority(
                "grow-coalition-trust",
                "network has no coalition that clearly stands out",
                "run more cooperative local>gonka>mimo paths and only promote coalition trust from strong outcomes",
            )
        )
    if int(resonance.get("count", 0) or 0) == 0:
        do_now.append(
            _priority(
                "seed-resonance-memory",
                "there is no resonance-route memory yet",
                "run a few strong non-reuse answers so the network can store verified reasoning routes",
            )
        )

    if not top_module:
        do_next.append(
            _priority(
                "rebuild-derived-modules",
                "no derived module is trusted enough to be useful",
                "create new derived modules only from high-quality cooperative runs with good goal alignment",
            )
        )
    elif top_module.get("state") != "active":
        do_next.append(
            _priority(
                "repair-derived-module",
                "best derived module is not active",
                "run care cycles and lower trust until the module returns to active state",
            )
        )

    if "route dominance risk" in risks:
        do_next.append(
            _priority(
                "controlled-exploration",
                "one route is becoming too dominant",
                "increase exploration slightly, but only after weak routes are pruned",
            )
        )

    if stale_modules:
        do_next.append(
            _priority(
                "retire-stale-modules",
                "stale derived modules are still present",
                "retire or refresh stale modules before creating more",
            )
        )

    if top_route:
        keep.append(
            _priority(
                "keep-top-route",
                "the route has the strongest pheromone and remains the best current backbone",
                "keep {route} as primary while improving adequacy and goal alignment".format(
                    route=top_route.get("route_key", "<none>")
                ),
            )
        )
    if strong_routes:
        keep.append(
            _priority(
                "keep-strong-routes",
                "some routes already meet strength criteria",
                "preserve strong routes and avoid unnecessary churn in their selection logic",
            )
        )
    if report.get("future_scenarios"):
        keep.append(
            _priority(
                "keep-scenarios",
                "future planner is already producing scenarios",
                "use the scenario list to judge whether the network is stabilizing or drifting after fixes",
            )
        )

    overall = "stabilize" if observer_status in {"watch", "intervene"} else "optimize"
    return {
        "overall_priority": overall,
        "do_now": do_now,
        "do_next": do_next,
        "keep": keep,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a prioritized fix plan from network health.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text output.")
    args = parser.parse_args()

    report = build_report()
    plan = build_fix_plan(report)

    if args.json:
        print(json.dumps({"report": report, "fix_plan": plan}, ensure_ascii=False, indent=2))
        return 0

    print(f"overall = {plan['overall_priority']}")
    print("do_now = {value}".format(value="; ".join(item["action"] for item in plan["do_now"]) or "<none>"))
    print("do_next = {value}".format(value="; ".join(item["action"] for item in plan["do_next"]) or "<none>"))
    print("keep = {value}".format(value="; ".join(item["action"] for item in plan["keep"]) or "<none>"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
