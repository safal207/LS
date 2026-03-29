# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.coalition_registry import CoalitionRecord, CoalitionRegistry
from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit
from graph.derived_module_registry import DerivedModuleRegistry
from graph.route_stats import RouteStats, RouteStatsStore
from network import TemporalTrajectoryLayer, TrajectoryStore


def test_temporal_trajectory_layer_builds_snapshot_record_and_scenarios(tmp_path):
    route_store = RouteStatsStore(tmp_path / "routes.json")
    route_store.save_route(
        RouteStats(
            route_key="full_run>local>gonka>mimo",
            pheromone_weight=0.7,
            runs=4,
            successes=4,
            avg_quality=0.82,
            avg_latency_ms=8500,
        )
    )
    route_store.save_route(
        RouteStats(
            route_key="full_run>cloud",
            pheromone_weight=0.02,
            runs=3,
            successes=0,
            avg_quality=0.4,
            avg_latency_ms=22000,
        )
    )

    coalition_registry = CoalitionRegistry(tmp_path / "coalitions.json")
    coalition_registry.save_coalition(
        CoalitionRecord(
            coalition_id="c1",
            route_key="full_run>local>gonka>mimo",
            members=["local", "gonka", "mimo"],
            trust_score=0.8,
            runs=3,
            successes=3,
            avg_quality=0.81,
        )
    )

    derived_registry = DerivedModuleRegistry(tmp_path / "derived.json")
    module = derived_registry.create_or_update_from_success(
        parent_coalition_id="c1",
        source_route_key="full_run>local>gonka>mimo",
        domain="generic",
        task_type="generic",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Keep concise answers.",
        quality_score=0.78,
    )
    module.state = "active"
    derived_registry.save_module(module)

    memory_store = MemoryGraphStore(tmp_path / "cases.jsonl")
    memory_store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="Почему вы выбрали этот стек?",
            intent="technical_reasoning",
            why="evaluate_reasoning",
            resonance_score=0.91,
            alignment_score=0.83,
        )
    )

    layer = TemporalTrajectoryLayer(
        store=TrajectoryStore(
            tmp_path / "trajectory.json",
            route_store=route_store,
            coalition_registry=coalition_registry,
            derived_module_registry=derived_registry,
            memory_store=memory_store,
        )
    )

    result = layer.evaluate()

    assert result.snapshot.route_health["count"] == 2
    assert result.snapshot.resonance_health["count"] == 1
    assert "resonance_unit_delta" in result.record.deltas
    assert result.record.trend in {"bootstrap", "stable", "improving", "degrading"}
    assert len(result.scenarios) == 3
