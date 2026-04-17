from __future__ import annotations

from modules.cognition.attachment_bond import AttachmentBond
from modules.graph.memory_store import MemoryGraphStore


def test_attachment_bond_defaults_are_safe() -> None:
    bond = AttachmentBond()
    assert 0.0 <= bond.attachment_strength <= 1.0
    assert 0.0 <= bond.attachment_stability <= 1.0
    assert bond.attachment_style in {"secure", "anxious", "avoidant", "disorganized"}


def test_memory_store_persists_attachment_bond(tmp_path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    bond = AttachmentBond(
        attachment_strength=0.77,
        attachment_style="secure",
        attachment_stability=0.66,
    )
    store.save_attachment_bond(bond)

    loaded = store.get_attachment_bond()
    assert loaded.attachment_strength == 0.77
    assert loaded.attachment_style == "secure"
    assert loaded.attachment_stability == 0.66


def test_memory_store_evolves_and_resets_attachment(tmp_path) -> None:
    store = MemoryGraphStore(tmp_path / "cases.jsonl")

    evolved = store.evolve_attachment_bond(
        conversation_frequency=0.9,
        conversation_quality=0.9,
        user_feedback_signal=0.9,
        omni_signal={"tone": "warm", "fatigue": 0.1},
        shared_relational_delta=0.8,
        source="test",
    )
    assert evolved.attachment_strength > 0.0
    assert store.get_attachment_arc(limit=5)
    assert store.get_attachment_audit(limit=5)

    reset = store.reset_attachment_bond(reason="test_soft_reset")
    assert reset.attachment_strength == 0.15
    assert reset.attachment_style == "secure"
