from __future__ import annotations

from modules.cognition.relational_self import RelationalSelfBuilder
from modules.council.council_engine import RelationalCouncilEngine
from modules.council.cycle_runner import CouncilCycleRunner
from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import RelationalEdge, ResonanceKnowledgeUnit


def test_council_cycle_uses_relational_self_and_detects_breach(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    unit = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="Contradiction-heavy state",
            resonance_score=0.25,
            alignment_score=0.2,
        )
    )
    store.store_relational_edge(
        unit.unit_id,
        RelationalEdge(
            target_unit_id=unit.unit_id,
            relation_type="contradicts",
            strength=0.95,
        ),
    )

    runner = CouncilCycleRunner(
        self_builder=RelationalSelfBuilder(store),
        engine=RelationalCouncilEngine(coherence_guard_threshold=0.5),
    )

    result = runner.run(cycle_id="cx-1", mode="self-preservation")

    assert result["relational_self"]["self_coherence_score"] < 0.5
    assert result["relational_breach"]["breach"] is True
    assert result["council_outcome"]["blocked"] is True
    assert result["constitution_record"] is not None
    history = store.get_constitution_history(limit=5)
    assert history
    assert history[-1]["cycle_id"] == "cx-1"


def test_council_engine_evolution_mode_returns_proposals(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="Need stronger coherence",
            resonance_score=0.45,
            alignment_score=0.4,
        )
    )
    runner = CouncilCycleRunner(
        self_builder=RelationalSelfBuilder(store),
        engine=RelationalCouncilEngine(),
    )

    result = runner.run(cycle_id="cx-2", mode="self-evolution-proposal")

    assert result["council_outcome"]["mode"] == "self-evolution-proposal"
    assert result["council_outcome"]["proposal_count"] >= 1
    assert result["council_outcome"]["actions"]
    assert result["constitution_record"] is not None
    assert result["council_outcome"]["constitution"]["schema_version"] == "1.0"


def test_evolution_auto_apply_blocked_by_constitution_violation(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="bad alignment",
            resonance_score=0.9,
            alignment_score=0.05,
        )
    )
    runner = CouncilCycleRunner(
        self_builder=RelationalSelfBuilder(store),
        engine=RelationalCouncilEngine(),
    )

    result = runner.run(
        cycle_id="cx-2b",
        mode="self-evolution-proposal",
        execute_actions=True,
    )

    assert result["policy_decision"]["allow_auto_apply"] is False
    assert result["policy_decision"]["requires_review"] is True
    assert result["policy_decision"]["reason"] == "constitution_violation"
    assert result["applied_actions"] == []


def test_council_runner_can_apply_evolution_actions(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    a = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="improve consistency",
            resonance_score=0.65,
            alignment_score=0.65,
        )
    )
    b = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="second node",
            resonance_score=0.6,
            alignment_score=0.6,
        )
    )
    store.store_relational_edge(
        a.unit_id,
        RelationalEdge(
            target_unit_id=b.unit_id,
            relation_type="reinforces",
            strength=0.3,
        ),
    )
    runner = CouncilCycleRunner(
        self_builder=RelationalSelfBuilder(store),
        engine=RelationalCouncilEngine(),
    )
    result = runner.run(
        cycle_id="cx-3",
        mode="self-evolution-proposal",
        execute_actions=True,
    )
    assert result["applied_actions"]
    assert result["policy_decision"]["allow_auto_apply"] is True
    updated_a = next(u for u in store.list_resonance_units() if u.unit_id == a.unit_id)
    reinforces = [
        rel for rel in updated_a.relations if rel.get("relation_type") == "reinforces"
    ]
    assert reinforces
    assert float(reinforces[0]["strength"]) > 0.3


def test_policy_decision_requires_review_for_escalate_violation():
    decision = CouncilCycleRunner._policy_decision(  # noqa: SLF001
        mode="self-evolution-proposal",
        outcome={
            "blocked": False,
            "constitution": {
                "passed": False,
                "findings": [
                    {"severity": "escalate", "passed": False},
                ],
            },
        },
    )
    assert decision["allow_auto_apply"] is False
    assert decision["requires_review"] is True
    assert decision["reason"] == "constitution_escalate_violation"


def test_council_action_rollback_restores_edge_strength(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    a = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="rollback consistency",
            resonance_score=0.6,
            alignment_score=0.6,
        )
    )
    b = store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="rollback node",
            resonance_score=0.61,
            alignment_score=0.61,
        )
    )
    store.store_relational_edge(
        a.unit_id,
        RelationalEdge(
            target_unit_id=b.unit_id,
            relation_type="reinforces",
            strength=0.35,
        ),
    )
    runner = CouncilCycleRunner(
        self_builder=RelationalSelfBuilder(store),
        engine=RelationalCouncilEngine(),
    )
    result = runner.run(
        cycle_id="cx-rb",
        mode="self-evolution-proposal",
        execute_actions=True,
    )
    action = next(item for item in result["applied_actions"] if item.get("action") == "increase_reinforcing_edge_strength")
    action_id = str(action["action_id"])
    updated = next(u for u in store.list_resonance_units() if u.unit_id == a.unit_id)
    updated_strength = next(rel["strength"] for rel in updated.relations if rel.get("relation_type") == "reinforces")
    assert float(updated_strength) > 0.35

    rollback = runner.rollback_action(action_id=action_id)
    assert rollback["rolled_back"] is True
    assert "relational_self_snapshot_id" in rollback

    rolled_back = next(u for u in store.list_resonance_units() if u.unit_id == a.unit_id)
    rolled_strength = next(rel["strength"] for rel in rolled_back.relations if rel.get("relation_type") == "reinforces")
    assert float(rolled_strength) == 0.35
