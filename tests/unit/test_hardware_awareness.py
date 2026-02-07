from __future__ import annotations

from pathlib import Path

from codex.causal_memory.engine import AdaptiveEngine
from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.layer import CausalMemoryLayer
from codex.causal_memory.store import MemoryStore
from codex.cognitive.context import TaskContext
from codex.cognitive.hardware import HardwareMonitor
from codex.cognitive.loop import UnifiedCognitiveLoop
from codex.cognitive.presence import PresenceMonitor
from codex.cognitive.thread import ThreadFactory
from codex.cognitive.decision import DecisionMemoryProtocol
from codex.cognitive.identity import LivingIdentity
from codex.cognitive.scheduler import ThreadScheduler
from codex.cognitive.thread import CognitiveThread
from codex.cognitive.workspace import GlobalFrame
from codex.registry.model_registry import ModelRegistry
from codex.capu.tracer import Tracer


class DummyModel:
    def __init__(self) -> None:
        self._hooks = []

    def register_forward_hook(self, hook):
        self._hooks.append(hook)

        class Handle:
            @staticmethod
            def remove():
                return None

        return Handle()

    def named_modules(self):
        return []

    def generate(self, payload):
        return {"text": "ok", "payload": payload}


class DummyLoader:
    def load_llm(self, _config):
        return DummyModel()

    def load_stt(self, _config):
        return DummyModel()

    def load_vad(self, _config):
        return DummyModel()

    def load_embeddings(self, _config):
        return {"type": "embeddings"}

    def load_custom(self, _config):
        return DummyModel()

    def unload(self, _model):
        return None


def test_hardware_state_added_to_constraints(monkeypatch, tmp_path: Path) -> None:
    registry = ModelRegistry(loader=DummyLoader())
    registry.register("dummy-llm", {"type": "llm", "path": "dummy"})
    memory_layer = CausalMemoryLayer(store_path=tmp_path / "memory.jsonl")
    loop = UnifiedCognitiveLoop(
        registry=registry,
        memory_layer=memory_layer,
        decision_protocol=DecisionMemoryProtocol(),
        presence_monitor=PresenceMonitor(),
        tracer=Tracer(),
        identity=LivingIdentity(),
        thread_factory=ThreadFactory(),
    )

    hardware_state = {
        "cpu_percent": 90.0,
        "cpu_temp": 80.0,
        "ram_used_gb": 7.2,
        "ram_total_gb": 8.0,
        "swap_used_gb": 0.4,
        "io_wait": 6.0,
    }
    monkeypatch.setattr(HardwareMonitor, "collect", lambda: hardware_state)

    ctx = TaskContext(
        task_type="chat",
        input_payload={"prompt": "hello"},
        constraints={},
        candidates=["dummy-llm"],
    )

    loop.run_task(ctx)

    assert ctx.constraints["hardware"] == hardware_state


def test_adaptive_engine_uses_hardware_for_strategy(tmp_path: Path) -> None:
    engine = AdaptiveEngine(MemoryStore(tmp_path / "memory.jsonl"), CausalGraph())
    strategy = engine.recommend_strategy(
        ["model-a"],
        context={
            "hardware": {
                "cpu_percent": 85.0,
                "ram_used_gb": 7.0,
                "ram_total_gb": 8.0,
                "cpu_temp": 70.0,
            }
        },
    )
    assert strategy == "conservative"


def test_scheduler_adjusts_attention_on_overload() -> None:
    scheduler = ThreadScheduler()
    heavy_thread = CognitiveThread(thread_id="heavy", priority=1.0, attention_weight=1.0)
    light_thread = CognitiveThread(thread_id="light", priority=0.8, attention_weight=1.0)
    scheduler.register_thread(heavy_thread)
    scheduler.register_thread(light_thread)

    frame = GlobalFrame(
        thread_id="heavy",
        task_type="chat",
        system_state="stable",
        self_model={},
        affective={},
        identity={},
        capu_features={},
        decision={},
        memory_refs={},
        narrative_refs={},
        merit_scores={"focus": 0.8},
        timestamp="2025-01-01T00:00:00+00:00",
        hardware={"cpu_percent": 90.0, "ram_used_gb": 7.0, "ram_total_gb": 8.0},
    )

    scheduler.update_attention(frame)

    assert heavy_thread.attention_weight < 1.0
    assert light_thread.attention_weight > 1.0
