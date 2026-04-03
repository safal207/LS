# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.care_cycle import CareCycleRunner
from graph.derived_module_registry import DerivedModuleRegistry
from graph.memory_store import MemoryGraphStore


def test_care_cycle_promotes_healthy_module(tmp_path):
    registry = DerivedModuleRegistry(tmp_path / "derived.json")
    module = registry.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="technical_reasoning",
        task_type="evaluate_reasoning",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Keep answers concise.",
        quality_score=0.84,
    )
    runner = CareCycleRunner(registry, min_quality=0.7, min_trust=0.6, retire_trust=0.3)

    result = runner.review(module.module_id)

    assert result is not None
    assert result.action in {"promote", "keep"}
    assert result.state == "active"


def test_care_cycle_stores_resonance_unit_for_active_healthy_module(tmp_path):
    registry = DerivedModuleRegistry(tmp_path / "derived.json")
    graph_store = MemoryGraphStore(tmp_path / "cases.jsonl")
    module = registry.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="technical_reasoning",
        task_type="evaluate_reasoning",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Keep answers concise.",
        quality_score=0.91,
    )
    runner = CareCycleRunner(
        registry,
        graph_store=graph_store,
        min_quality=0.7,
        min_trust=0.6,
        retire_trust=0.3,
    )

    result = runner.review(
        module.module_id,
        cycle_id="cycle-001",
        source_question="How should I explain the trade-off?",
        intent="architecture",
        why="compare trade-offs",
        goal_vector=[0.8, 0.6],
        causal_path=[
            {
                "step": "strategy_selected",
                "strategy": "compare_options",
                "outcome": "clear_tradeoff_explanation",
            }
        ],
        resonance_score=0.93,
        alignment_score=0.88,
    )

    assert result is not None
    assert result.state == "active"
    saved_units = graph_store.list_resonance_units()
    assert len(saved_units) == 1
    assert saved_units[0].source_question == "How should I explain the trade-off?"
    assert saved_units[0].intent == "architecture"
    assert saved_units[0].why == "compare trade-offs"
    assert saved_units[0].metadata.get("source") == "care_cycle"
    assert saved_units[0].metadata.get("cycle_id") == "cycle-001"


def test_care_cycle_demotes_and_retires_weak_module(tmp_path):
    registry = DerivedModuleRegistry(tmp_path / "derived.json")
    module = registry.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="generic",
        task_type="generic",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Weak policy.",
        quality_score=0.4,
    )
    module.trust_score = 0.2
    module.runs = 3
    module.successes = 0
    registry.save_module(module)
    runner = CareCycleRunner(registry, min_quality=0.7, min_trust=0.6, retire_trust=0.3)

    result = runner.review(module.module_id)

    assert result is not None
    assert result.action == "retire"
    assert result.state == "retired"


def test_care_cycle_store_resonance_unit_is_best_effort(tmp_path):
    class _ExplodingStore:
        def store_resonance_unit(self, _unit):
            raise RuntimeError("boom")

    registry = DerivedModuleRegistry(tmp_path / "derived.json")
    module = registry.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="generic",
        task_type="generic",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="ok",
        quality_score=0.9,
    )
    runner = CareCycleRunner(
        registry,
        graph_store=_ExplodingStore(),
        min_quality=0.7,
        min_trust=0.6,
        retire_trust=0.3,
    )

    result = runner.review(
        module.module_id,
        source_question="what is on screen",
        resonance_score=0.9,
    )

    assert result is not None
    assert result.state == "active"


def test_care_cycle_does_not_store_resonance_unit_for_retired_module(tmp_path):
    registry = DerivedModuleRegistry(tmp_path / "derived.json")
    graph_store = MemoryGraphStore(tmp_path / "cases.jsonl")
    module = registry.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="generic",
        task_type="generic",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Weak policy.",
        quality_score=0.4,
    )
    module.trust_score = 0.2
    module.runs = 3
    module.successes = 0
    registry.save_module(module)

    runner = CareCycleRunner(
        registry,
        graph_store=graph_store,
        min_quality=0.7,
        min_trust=0.6,
        retire_trust=0.3,
    )

    result = runner.review(
        module.module_id,
        source_question="what is on screen",
        resonance_score=0.95,
    )

    assert result is not None
    assert result.state == "retired"
    assert graph_store.list_resonance_units() == []
