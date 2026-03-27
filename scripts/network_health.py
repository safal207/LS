from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "python" / "modules"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from config import (  # noqa: E402
    GRAPH_COALITION_STORE_PATH,
    GRAPH_DERIVED_MODULE_STORE_PATH,
    GRAPH_TRAIL_STORE_PATH,
)
from graph import CoalitionRegistry, DerivedModuleRegistry, RouteStatsStore  # noqa: E402
from network import NetworkObserver  # noqa: E402


def _top_route(route_store: RouteStatsStore) -> dict[str, Any] | None:
    routes = route_store.list_routes()
    if not routes:
        return None
    routes.sort(
        key=lambda item: (
            item.pheromone_weight,
            item.avg_quality,
            item.avg_goal_alignment,
            item.runs,
        ),
        reverse=True,
    )
    top = routes[0]
    return {
        "route_key": top.route_key,
        "pheromone_weight": top.pheromone_weight,
        "avg_quality": top.avg_quality,
        "avg_goal_alignment": top.avg_goal_alignment,
        "runs": top.runs,
        "avg_latency_ms": top.avg_latency_ms,
    }


def _top_coalition(registry: CoalitionRegistry) -> dict[str, Any] | None:
    coalitions = registry.list_coalitions()
    if not coalitions:
        return None
    coalitions.sort(
        key=lambda item: (item.trust_score, item.avg_quality, item.successes, item.runs),
        reverse=True,
    )
    top = coalitions[0]
    return {
        "coalition_id": top.coalition_id,
        "route_key": top.route_key,
        "members": top.members,
        "trust_score": top.trust_score,
        "avg_quality": top.avg_quality,
        "runs": top.runs,
    }


def _top_derived_module(registry: DerivedModuleRegistry) -> dict[str, Any] | None:
    modules = registry.list_modules()
    if not modules:
        return None
    modules.sort(
        key=lambda item: (item.trust_score, item.quality_score, item.usage_count, item.successes),
        reverse=True,
    )
    top = modules[0]
    return {
        "module_id": top.module_id,
        "state": top.state,
        "preferred_backend": top.preferred_backend,
        "trust_score": top.trust_score,
        "quality_score": top.quality_score,
        "usage_count": top.usage_count,
        "parent_coalition_id": top.parent_coalition_id,
    }


def build_report() -> dict[str, Any]:
    route_store = RouteStatsStore(GRAPH_TRAIL_STORE_PATH)
    coalition_registry = CoalitionRegistry(GRAPH_COALITION_STORE_PATH)
    derived_registry = DerivedModuleRegistry(GRAPH_DERIVED_MODULE_STORE_PATH)
    observer = NetworkObserver()
    report = observer.evaluate().to_dict()
    retrospective = report.get("retrospective") or {}
    trajectory = report.get("trajectory") or {}
    adequacy = report.get("adequacy") or {}

    return {
        "observer_status": report.get("status"),
        "observer_summary": report.get("summary"),
        "adequacy_status": adequacy.get("status"),
        "adequacy_risks": adequacy.get("risks"),
        "trajectory_trend": ((trajectory.get("record") or {}).get("trend")),
        "trajectory_snapshot_id": ((trajectory.get("snapshot") or {}).get("snapshot_id")),
        "top_route": _top_route(route_store),
        "strong_routes": retrospective.get("strong_routes"),
        "weak_routes": retrospective.get("weak_routes"),
        "top_coalition": _top_coalition(coalition_registry),
        "strong_coalitions": retrospective.get("strong_coalitions"),
        "weak_coalitions": retrospective.get("weak_coalitions"),
        "top_derived_module": _top_derived_module(derived_registry),
        "stale_modules": retrospective.get("stale_modules"),
        "future_scenarios": [item.get("title") for item in (trajectory.get("scenarios") or [])],
        "store_paths": {
            "routes": GRAPH_TRAIL_STORE_PATH,
            "coalitions": GRAPH_COALITION_STORE_PATH,
            "derived_modules": GRAPH_DERIVED_MODULE_STORE_PATH,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Show current network health and observer summary.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text output.")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"observer.status = {report['observer_status']}")
    print(f"adequacy.status = {report['adequacy_status']}")
    print(f"trajectory.trend = {report['trajectory_trend']}")
    print(f"trajectory.snapshot_id = {report['trajectory_snapshot_id']}")

    top_route = report["top_route"] or {}
    print(
        "route.active = {route}  pheromone={pheromone}  quality={quality}  goal_alignment={goal_alignment}  runs={runs}".format(
            route=top_route.get("route_key", "<none>"),
            pheromone=top_route.get("pheromone_weight", 0.0),
            quality=top_route.get("avg_quality", 0.0),
            goal_alignment=top_route.get("avg_goal_alignment", 0.0),
            runs=top_route.get("runs", 0),
        )
    )

    top_coalition = report["top_coalition"] or {}
    print(
        "coalition.active = {coalition}  route={route}  trust={trust}  members={members}".format(
            coalition=top_coalition.get("coalition_id", "<none>"),
            route=top_coalition.get("route_key", "<none>"),
            trust=top_coalition.get("trust_score", 0.0),
            members=", ".join(top_coalition.get("members", [])) or "<none>",
        )
    )

    top_module = report["top_derived_module"] or {}
    print(
        "derived.active = {module}  backend={backend}  state={state}  trust={trust}  quality={quality}".format(
            module=top_module.get("module_id", "<none>"),
            backend=top_module.get("preferred_backend", "<none>"),
            state=top_module.get("state", "<none>"),
            trust=top_module.get("trust_score", 0.0),
            quality=top_module.get("quality_score", 0.0),
        )
    )

    print("observer.risks = {risks}".format(risks=", ".join(report.get("adequacy_risks") or []) or "<none>"))
    print("routes.strong = {value}".format(value=", ".join(report.get("strong_routes") or []) or "<none>"))
    print("routes.weak = {value}".format(value=", ".join(report.get("weak_routes") or []) or "<none>"))
    print("coalitions.strong = {value}".format(value=", ".join(report.get("strong_coalitions") or []) or "<none>"))
    print("modules.stale = {value}".format(value=", ".join(report.get("stale_modules") or []) or "<none>"))
    print("future.scenarios = {value}".format(value=", ".join(report.get("future_scenarios") or []) or "<none>"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
