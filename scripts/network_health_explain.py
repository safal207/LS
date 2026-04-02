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


def build_explanation(report: dict[str, Any]) -> dict[str, Any]:
    top_route = report.get("top_route") or {}
    top_coalition = report.get("top_coalition") or {}
    top_module = report.get("top_derived_module") or {}
    resonance = report.get("resonance_units") or {}
    top_unit = resonance.get("top_unit") or {}
    risks = list(report.get("adequacy_risks") or [])
    weak_routes = list(report.get("weak_routes") or [])
    strong_routes = list(report.get("strong_routes") or [])
    future_scenarios = list(report.get("future_scenarios") or [])

    good: list[str] = []
    bad: list[str] = []
    next_actions: list[str] = []

    if top_route:
        good.append(
            "active route is {route} with pheromone {pheromone} and quality {quality}".format(
                route=top_route.get("route_key"),
                pheromone=top_route.get("pheromone_weight", 0.0),
                quality=top_route.get("avg_quality", 0.0),
            )
        )
    else:
        bad.append("no active route history yet")
        next_actions.append("run the system on a few real questions to accumulate route history")

    if resonance.get("count", 0):
        good.append(
            "resonance memory has {count} units; top unit tracks intent {intent} with score {score}".format(
                count=resonance.get("count", 0),
                intent=top_unit.get("intent", "<none>"),
                score=top_unit.get("resonance_score", 0.0),
            )
        )
    else:
        bad.append("no resonance knowledge units have been stored yet")
        next_actions.append("collect more strong non-reuse answers so the network can store verified reasoning routes")

    if strong_routes:
        good.append("strong routes exist: " + ", ".join(strong_routes))

    if weak_routes:
        bad.append("weak routes detected: " + ", ".join(weak_routes))
        next_actions.append("prune or demote weak routes from preferred selection")

    if top_coalition:
        good.append(
            "top coalition {coalition} has trust {trust}".format(
                coalition=top_coalition.get("coalition_id"),
                trust=top_coalition.get("trust_score", 0.0),
            )
        )
    else:
        bad.append("no coalition is currently strong enough to stand out")
        next_actions.append("collect more cooperative runs before promoting coalition trust")

    if top_module:
        if top_module.get("state") == "active":
            good.append(
                "best derived module {module} is active on backend {backend}".format(
                    module=top_module.get("module_id"),
                    backend=top_module.get("preferred_backend"),
                )
            )
        else:
            bad.append(
                "best derived module {module} is not active".format(
                    module=top_module.get("module_id")
                )
            )
            next_actions.append("run care cycles or lower trust for unstable derived modules")
    else:
        bad.append("no derived module is currently trusted enough")
        next_actions.append("grow new derived modules only from strong cooperative runs")

    if report.get("observer_status") == "stable":
        good.append("observer sees the network inside the tuning fork")
    else:
        bad.append(
            "observer status is {status}".format(status=report.get("observer_status"))
        )

    if risks:
        bad.extend(risks)
        if "adequacy below tuning fork" in risks:
            next_actions.append("raise answer adequacy before increasing route trust")
        if "too many weak routes" in risks:
            next_actions.append("reduce exploration noise and stop reinforcing weak routes")

    if future_scenarios:
        good.append("future planner produced scenarios: " + ", ".join(future_scenarios))

    summary = (
        "network is {status}; active route is {route}; main risk is {risk}".format(
            status=report.get("observer_status"),
            route=top_route.get("route_key", "<none>"),
            risk=risks[0] if risks else "no major risk",
        )
    )

    dedup_next: list[str] = []
    seen = set()
    for item in next_actions:
        if item not in seen:
            seen.add(item)
            dedup_next.append(item)

    return {
        "summary": summary,
        "good": good,
        "bad": bad,
        "next_actions": dedup_next,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain current network health in plain text.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text output.")
    args = parser.parse_args()

    report = build_report()
    explanation = build_explanation(report)

    if args.json:
        print(
            json.dumps(
                {
                    "report": report,
                    "explanation": explanation,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print("summary = {value}".format(value=explanation["summary"]))
    print("good = {value}".format(value="; ".join(explanation["good"]) or "<none>"))
    print("bad = {value}".format(value="; ".join(explanation["bad"]) or "<none>"))
    print("next = {value}".format(value="; ".join(explanation["next_actions"]) or "<none>"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
