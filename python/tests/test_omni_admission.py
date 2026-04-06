# ruff: noqa: E402
"""Tests for the background resonance admission gate.

Covers:
  - ResonanceAdmissionPolicy defaults and effective_resonance_threshold
  - ResonanceAdmissionGate: resonance threshold, alignment threshold, rate cap,
    provider-aware thresholds, thread safety, pending_writes_in_window
  - QwenOmniWorker integration: gate respected, gate blocks, custom gate injected
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit
from omni.admission import (
    AdmissionDecision,
    ResonanceAdmissionGate,
    ResonanceAdmissionPolicy,
)
from omni.qwen_omni_worker import QwenOmniWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit(resonance: float = 0.5, alignment: float = 0.0, provider: str = "") -> ResonanceKnowledgeUnit:
    return ResonanceKnowledgeUnit(
        source_question="test",
        resonance_score=resonance,
        alignment_score=alignment,
        metadata={"provider": provider} if provider else {},
    )


# ---------------------------------------------------------------------------
# ResonanceAdmissionPolicy
# ---------------------------------------------------------------------------


def test_policy_defaults():
    p = ResonanceAdmissionPolicy()
    assert p.min_resonance_score == 0.3
    assert p.fallback_min_resonance_score == 0.5
    assert p.min_alignment_score == 0.0
    assert p.max_writes_per_window == 10
    assert p.window_seconds == 60.0


def test_policy_threshold_fallback_provider():
    p = ResonanceAdmissionPolicy(min_resonance_score=0.3, fallback_min_resonance_score=0.6)
    assert p.effective_resonance_threshold("fallback") == 0.6


def test_policy_threshold_trusted_provider():
    p = ResonanceAdmissionPolicy(min_resonance_score=0.3, fallback_min_resonance_score=0.6)
    assert p.effective_resonance_threshold("dashscope") == 0.3


def test_policy_threshold_unknown_provider_uses_standard():
    p = ResonanceAdmissionPolicy(min_resonance_score=0.3, fallback_min_resonance_score=0.6)
    assert p.effective_resonance_threshold("some_unknown") == 0.3


# ---------------------------------------------------------------------------
# AdmissionDecision
# ---------------------------------------------------------------------------


def test_decision_bool_true():
    assert bool(AdmissionDecision(allowed=True, reason="ok")) is True


def test_decision_bool_false():
    assert bool(AdmissionDecision(allowed=False, reason="nope")) is False


def test_decision_is_frozen():
    import pytest

    d = AdmissionDecision(allowed=True, reason="ok")
    with pytest.raises((AttributeError, TypeError)):
        d.allowed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResonanceAdmissionGate — resonance threshold
# ---------------------------------------------------------------------------


def test_gate_allows_above_threshold():
    gate = ResonanceAdmissionGate(ResonanceAdmissionPolicy(min_resonance_score=0.3))
    decision = gate.admit(_unit(resonance=0.4))
    assert decision.allowed


def test_gate_blocks_at_threshold():
    gate = ResonanceAdmissionGate(ResonanceAdmissionPolicy(min_resonance_score=0.3))
    decision = gate.admit(_unit(resonance=0.29))
    assert not decision.allowed
    assert "resonance" in decision.reason


def test_gate_exact_threshold_blocked():
    # threshold is strict (<), not (<=)
    gate = ResonanceAdmissionGate(ResonanceAdmissionPolicy(min_resonance_score=0.3))
    decision = gate.admit(_unit(resonance=0.3))
    # 0.3 < 0.3 is False → allowed (equal meets threshold)
    assert decision.allowed


# ---------------------------------------------------------------------------
# ResonanceAdmissionGate — provider-aware threshold
# ---------------------------------------------------------------------------


def test_gate_fallback_uses_stricter_threshold():
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.3,
            fallback_min_resonance_score=0.6,
        )
    )
    # resonance=0.4 passes standard but not fallback
    decision = gate.admit(_unit(resonance=0.4, provider="fallback"))
    assert not decision.allowed
    assert "provider='fallback'" in decision.reason


def test_gate_fallback_passes_above_fallback_threshold():
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.3,
            fallback_min_resonance_score=0.5,
        )
    )
    decision = gate.admit(_unit(resonance=0.6, provider="fallback"))
    assert decision.allowed


def test_gate_dashscope_uses_standard_threshold():
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.3,
            fallback_min_resonance_score=0.9,
        )
    )
    # dashscope is trusted — uses standard 0.3, not 0.9
    decision = gate.admit(_unit(resonance=0.35, provider="dashscope"))
    assert decision.allowed


# ---------------------------------------------------------------------------
# ResonanceAdmissionGate — alignment threshold
# ---------------------------------------------------------------------------


def test_gate_alignment_check_disabled_by_default():
    gate = ResonanceAdmissionGate(ResonanceAdmissionPolicy(min_alignment_score=0.0))
    decision = gate.admit(_unit(resonance=0.5, alignment=0.0))
    assert decision.allowed


def test_gate_blocks_below_alignment_threshold():
    gate = ResonanceAdmissionGate(ResonanceAdmissionPolicy(min_alignment_score=0.4))
    decision = gate.admit(_unit(resonance=0.5, alignment=0.2))
    assert not decision.allowed
    assert "alignment" in decision.reason


def test_gate_allows_above_alignment_threshold():
    gate = ResonanceAdmissionGate(ResonanceAdmissionPolicy(min_alignment_score=0.4))
    decision = gate.admit(_unit(resonance=0.5, alignment=0.5))
    assert decision.allowed


# ---------------------------------------------------------------------------
# ResonanceAdmissionGate — rate cap
# ---------------------------------------------------------------------------


def test_gate_rate_cap_blocks_after_limit():
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.0,
            max_writes_per_window=3,
            window_seconds=60.0,
        )
    )
    for _ in range(3):
        d = gate.admit(_unit(resonance=0.9))
        assert d.allowed

    blocked = gate.admit(_unit(resonance=0.9))
    assert not blocked.allowed
    assert "rate cap" in blocked.reason


def test_gate_pending_writes_in_window():
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(min_resonance_score=0.0, max_writes_per_window=5)
    )
    assert gate.pending_writes_in_window() == 0
    gate.admit(_unit(resonance=0.9))
    gate.admit(_unit(resonance=0.9))
    assert gate.pending_writes_in_window() == 2


def test_gate_rate_cap_resets_after_window(monkeypatch):
    """After the window expires the counter resets and new writes are accepted."""
    import time

    calls: list[float] = [0.0]

    original_monotonic = time.monotonic

    def _fake_monotonic() -> float:
        return calls[0]

    monkeypatch.setattr(time, "monotonic", _fake_monotonic)

    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.0,
            max_writes_per_window=2,
            window_seconds=10.0,
        )
    )

    gate.admit(_unit(resonance=0.9))
    gate.admit(_unit(resonance=0.9))
    assert not gate.admit(_unit(resonance=0.9)).allowed

    # Advance clock past the window.
    calls[0] = 11.0
    d = gate.admit(_unit(resonance=0.9))
    assert d.allowed, f"Expected allowed after window reset, got: {d.reason}"

    monkeypatch.setattr(time, "monotonic", original_monotonic)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


def test_gate_thread_safe_rate_cap():
    """Concurrent admits from multiple threads must not exceed max_writes_per_window."""
    import threading

    policy = ResonanceAdmissionPolicy(
        min_resonance_score=0.0,
        max_writes_per_window=10,
        window_seconds=60.0,
    )
    gate = ResonanceAdmissionGate(policy)
    allowed_count = 0
    lock = threading.Lock()

    def _admit_many():
        nonlocal allowed_count
        for _ in range(20):
            d = gate.admit(_unit(resonance=0.9))
            if d.allowed:
                with lock:
                    allowed_count += 1

    threads = [threading.Thread(target=_admit_many) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert allowed_count == 10, f"Expected exactly 10 admitted, got {allowed_count}"


# ---------------------------------------------------------------------------
# QwenOmniWorker integration
# ---------------------------------------------------------------------------


def test_worker_uses_admission_gate(tmp_path, monkeypatch):
    """Worker with a permissive gate stores the unit."""
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.0,
            fallback_min_resonance_score=0.0,
            max_writes_per_window=100,
        )
    )
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "hello",
        admission_gate=gate,
    )
    unit = worker.capture_and_analyze(trigger="test")
    assert unit is not None
    assert len(store.list_resonance_units()) == 1


def test_worker_gate_blocks_low_resonance(tmp_path, monkeypatch):
    """Worker with a very strict gate drops the fallback insight."""
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    # The fallback provider (no screen) produces resonance 0.12.
    # Set fallback threshold higher so it gets blocked.
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.9,
            fallback_min_resonance_score=0.9,
        )
    )
    worker = QwenOmniWorker(
        graph_store=store,
        admission_gate=gate,
    )
    unit = worker.capture_and_analyze(trigger="test")
    assert unit is None
    assert len(store.list_resonance_units()) == 0


def test_worker_gate_blocks_after_rate_cap(tmp_path, monkeypatch):
    """After max_writes the gate blocks further stores."""
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    gate = ResonanceAdmissionGate(
        ResonanceAdmissionPolicy(
            min_resonance_score=0.0,
            fallback_min_resonance_score=0.0,
            max_writes_per_window=2,
            window_seconds=60.0,
        )
    )
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "hello",
        admission_gate=gate,
    )
    # Force FPS throttle off by resetting last frame timestamp before each call.
    for _ in range(3):
        worker._last_frame_ts = 0.0
        worker.capture_and_analyze(trigger="test")

    assert len(store.list_resonance_units()) == 2


def test_worker_default_gate_preserves_existing_behaviour(tmp_path, monkeypatch):
    """Worker without explicit gate builds one from min_store_resonance_score."""
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    # The fallback insight (no screen) has resonance 0.12.
    # Passing min_store_resonance_score=0.0 should still admit it.
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "hello",
        min_store_resonance_score=0.0,
    )
    unit = worker.capture_and_analyze(trigger="test")
    assert unit is not None
