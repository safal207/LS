import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.coalition_registry import CoalitionRecord, CoalitionRegistry
from graph.derived_module_registry import DerivedModuleRegistry
from graph.route_stats import RouteStats, RouteStatsStore
from retrospective import RetrospectiveCouncil


def test_retrospective_council_builds_report(tmp_path):
    route_store = RouteStatsStore(tmp_path / "routes.json")
    route_store.save_route(
        RouteStats(
            route_key="full_run>local>gonka>mimo",
            pheromone_weight=0.8,
            runs=4,
            successes=4,
            avg_quality=0.82,
            avg_goal_alignment=0.81,
        )
    )
    route_store.save_route(
        RouteStats(
            route_key="full_run>cloud",
            pheromone_weight=0.01,
            runs=3,
            successes=0,
            avg_quality=0.42,
            avg_goal_alignment=0.34,
        )
    )

    coalition_registry = CoalitionRegistry(tmp_path / "coalitions.json")
    coalition_registry.save_coalition(
        CoalitionRecord(
            coalition_id="c-strong",
            route_key="full_run>local>gonka>mimo",
            members=["local", "gonka", "mimo"],
            trust_score=0.82,
            runs=3,
            successes=3,
            avg_quality=0.8,
        )
    )

    derived_registry = DerivedModuleRegistry(tmp_path / "derived.json")
    stale = derived_registry.create_or_update_from_success(
        parent_coalition_id="c-strong",
        source_route_key="full_run>local>gonka>mimo",
        domain="generic",
        task_type="generic",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="weak",
        quality_score=0.4,
    )
    stale.state = "review"
    stale.trust_score = 0.3
    derived_registry.save_module(stale)

    council = RetrospectiveCouncil(
        route_store=route_store,
        coalition_registry=coalition_registry,
        derived_module_registry=derived_registry,
    )

    report = council.analyze()

    assert "full_run>local>gonka>mimo" in report.strong_routes
    assert "full_run>cloud" in report.weak_routes
    assert "full_run>local>gonka>mimo" in report.strong_coalitions
    assert stale.module_id in report.stale_modules
    assert report.recommendations
