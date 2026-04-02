# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.memory_store import MemoryGraphStore
from omni.qwen_omni_worker import QwenOmniWorker


def test_qwen_omni_worker_fallback_stores_unit(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=lambda: "user says hello",
        min_store_resonance_score=0.0,
    )

    unit = worker.capture_and_analyze(trigger="test")

    assert unit is not None
    assert unit.metadata.get("source") == "qwen_omni_worker"
    saved = store.list_resonance_units()
    assert len(saved) == 1
    assert saved[0].resonance_score >= 0.0


def test_qwen_omni_worker_skips_low_signal_fallback_unit(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    worker = QwenOmniWorker(
        graph_store=store,
        audio_provider=None,
        min_store_resonance_score=0.3,
    )

    monkeypatch.setattr(
        worker,
        "_capture_screen_frame",
        lambda: (None, {"capture": "unavailable", "reason": "test"}),
    )

    unit = worker.capture_and_analyze(trigger="test")

    assert unit is None
    assert store.list_resonance_units() == []
