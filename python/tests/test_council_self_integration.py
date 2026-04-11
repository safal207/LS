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
