from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.network_health import build_report  # noqa: E402
from scripts.network_health_explain import build_explanation  # noqa: E402
from scripts.network_health_fix_plan import build_fix_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified network dashboard for health, explanation, and fix plan.")
    parser.add_argument("--json", action="store_true", help="Print one combined JSON payload.")
    parser.add_argument(
        "--section",
        choices=["all", "health", "explain", "fix"],
        default="all",
        help="Print only one section or all sections.",
    )
    args = parser.parse_args()

    report = build_report()
    explanation = build_explanation(report)
    fix_plan = build_fix_plan(report)

    payload = {
        "health": report,
        "explain": explanation,
        "fix": fix_plan,
    }

    if args.json:
        if args.section == "all":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(payload[args.section], ensure_ascii=False, indent=2))
        return 0

    if args.section in {"all", "health"}:
        print("[health]")
        print(f"observer.status = {report['observer_status']}")
        print(f"adequacy.status = {report['adequacy_status']}")
        print(f"trajectory.trend = {report['trajectory_trend']}")
        top_route = report.get("top_route") or {}
        print(
            "route.active = {route}  pheromone={pheromone}  quality={quality}  goal_alignment={goal_alignment}".format(
                route=top_route.get("route_key", "<none>"),
                pheromone=top_route.get("pheromone_weight", 0.0),
                quality=top_route.get("avg_quality", 0.0),
                goal_alignment=top_route.get("avg_goal_alignment", 0.0),
            )
        )
        resonance = report.get("resonance_units") or {}
        top_unit = resonance.get("top_unit") or {}
        print(
            "resonance.units = {count}  top_intent={intent}  top_why={why}  score={score}".format(
                count=resonance.get("count", 0),
                intent=top_unit.get("intent", "<none>"),
                why=top_unit.get("why", "<none>"),
                score=top_unit.get("resonance_score", 0.0),
            )
        )
        print("")

    if args.section in {"all", "explain"}:
        print("[explain]")
        print(f"summary = {explanation['summary']}")
        print("good = {value}".format(value="; ".join(explanation["good"]) or "<none>"))
        print("bad = {value}".format(value="; ".join(explanation["bad"]) or "<none>"))
        print("")

    if args.section in {"all", "fix"}:
        print("[fix]")
        print(f"overall = {fix_plan['overall_priority']}")
        print("do_now = {value}".format(value="; ".join(item["action"] for item in fix_plan["do_now"]) or "<none>"))
        print("do_next = {value}".format(value="; ".join(item["action"] for item in fix_plan["do_next"]) or "<none>"))
        print("keep = {value}".format(value="; ".join(item["action"] for item in fix_plan["keep"]) or "<none>"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
