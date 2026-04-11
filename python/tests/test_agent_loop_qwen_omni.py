# ruff: noqa: E402
import queue
import sys
import threading
import time
import types
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

_lthread_stub = types.SimpleNamespace(capture_trace=lambda *_a, **_k: {})
sys.modules.setdefault("lthread", _lthread_stub)
sys.modules.setdefault("python.modules.lthread", _lthread_stub)

from agent import loop as loop_module


class _DummyIntentBus:
    def subscribe(self, _handler):
        return None


class _DummyVisionSubsystem:
    def __init__(self):
        self.intent_bus = _DummyIntentBus()

    def start(self):
        return None

    def stop(self):
        return None


class _DummyOmniWorker:
    started = 0
    stopped = 0

    def __init__(self, **_kwargs):
        self._running = False

    def start(self):
        self._running = True
        _DummyOmniWorker.started += 1

    def stop(self):
        self._running = False
        _DummyOmniWorker.stopped += 1


def test_agent_loop_starts_and_stops_qwen_worker(monkeypatch):
    monkeypatch.setenv("QWEN_OMNI_ENABLED", "1")
    monkeypatch.setattr(loop_module, "VisionSubsystem", _DummyVisionSubsystem)
    monkeypatch.setitem(sys.modules, "omni", types.SimpleNamespace(QwenOmniWorker=_DummyOmniWorker))

    q: queue.Queue = queue.Queue()
    agent = loop_module.AgentLoop(input_queue=q, handler=lambda text: f"echo:{text}")

    t = threading.Thread(target=agent.run, daemon=True)
    t.start()
    q.put({"type": "question", "text": "ping", "timestamp": 0.0})
    time.sleep(0.05)
    agent.stop()
    t.join(timeout=1.0)

    assert _DummyOmniWorker.started >= 1
    assert _DummyOmniWorker.stopped >= 1


def test_agent_loop_strategy_context_accepts_operator_profile(monkeypatch):
    monkeypatch.setattr(loop_module, "VisionSubsystem", _DummyVisionSubsystem)
    agent = loop_module.AgentLoop(handler=lambda text: f"echo:{text}")

    messages = [{"role": "user", "content": "help"}]
    enriched = agent._inject_strategy_context(
        messages,
        {
            "_operator_profile": {
                "questions_seen": 3,
                "pressure_level": 0.5,
                "prefers_examples": True,
                "interrupt_count": 1,
            }
        },
    )

    assert len(enriched) == 2
    assert enriched[-1]["role"] == "system"
    assert "давление 50%" in enriched[-1]["content"]
    assert "любит конкретные кейсы" in enriched[-1]["content"]


def test_relational_learning_loop_cleanup_keeps_recent_files(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(loop_module, "VisionSubsystem", _DummyVisionSubsystem)
    agent = loop_module.AgentLoop(handler=lambda text: text)
    artifact_dir = tmp_path / "rel-learning-loop"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    agent._relational_learning_artifact_dir = artifact_dir
    agent._relational_learning_max_artifacts = 2

    for idx in range(4):
        path = artifact_dir / f"scheduler-20260101-00000{idx}.json"
        path.write_text(json.dumps({"idx": idx}), encoding="utf-8")
        time.sleep(0.01)

    agent._cleanup_relational_learning_loop_artifacts()

    files = sorted(artifact_dir.glob("scheduler-*.json"))
    assert len(files) == 2
    assert files[-1].name.endswith("3.json")


def test_relational_learning_loop_snapshot_writer_creates_artifact(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(loop_module, "VisionSubsystem", _DummyVisionSubsystem)
    agent = loop_module.AgentLoop(handler=lambda text: text)
    artifact_dir = tmp_path / "rel-learning-loop"
    agent._relational_learning_artifact_dir = artifact_dir

    agent._write_relational_learning_loop_snapshot({"proposal_count": 1, "proposals": []})

    files = list(artifact_dir.glob("scheduler-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["source"] == "agent_loop_scheduler"
