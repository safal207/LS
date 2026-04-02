# ruff: noqa: E402
import queue
import sys
import threading
import time
import types
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
