from __future__ import annotations

from types import SimpleNamespace

from ls.agent_shell.cognitive_state import CognitiveStateBridge
from modules.cognition.attachment_bond import AttachmentBond
from modules.cognition.emotional_bonding_engine import EmotionalBondingEvolutionEngine
from modules.graph.memory_store import MemoryGraphStore


def test_engine_evolution_creates_milestone_and_repair_actions() -> None:
    engine = EmotionalBondingEvolutionEngine()

    bond = AttachmentBond(attachment_strength=0.79, attachment_stability=0.7)
    evolved = engine.evolve(
        bond,
        conversation_frequency=1.0,
        conversation_quality=1.0,
        user_feedback_signal=1.0,
        omni_signal={"tone": "warm", "fatigue": 0.0},
        shared_relational_delta=1.0,
    )
    assert evolved.attachment_strength >= 0.8
    assert evolved.bonding_milestones

    low = AttachmentBond(attachment_strength=0.25, attachment_stability=0.6)
    repaired = engine.evolve(
        low,
        conversation_frequency=0.0,
        conversation_quality=0.0,
        user_feedback_signal=0.0,
        omni_signal={"tone": "neutral", "fatigue": 1.0},
        shared_relational_delta=0.0,
    )
    assert repaired.repair_actions


def test_cognitive_bridge_exposes_attachment_resources(tmp_path, monkeypatch) -> None:
    store_path = tmp_path / "cases.jsonl"
    store = MemoryGraphStore(store_path)
    store.evolve_attachment_bond(
        conversation_frequency=0.8,
        conversation_quality=0.7,
        user_feedback_signal=0.9,
        omni_signal={"tone": "supportive", "fatigue": 0.2},
        shared_relational_delta=0.7,
        source="test",
    )

    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(store_path))
    bridge = CognitiveStateBridge(task_manager=SimpleNamespace())

    bond_payload = bridge.get_attachment_bond()
    assert bond_payload["resource"] == "self/attachment-bond"
    assert "bond" in bond_payload

    arc_payload = bridge.get_emotional_bonding_arc(limit=20)
    assert arc_payload["resource"] == "self/emotional-bonding-arc"
    assert arc_payload["arc"]

    insight = bridge.get_attachment_insight("Как изменилась наша связь?", window=20)
    assert insight["resource"] == "self/attachment-insight"
    assert "attachment_strength" in insight["insight"]
