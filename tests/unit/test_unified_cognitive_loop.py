from __future__ import annotations

from pathlib import Path

from codex.capu.tracer import Tracer
from codex.causal_memory.layer import CausalMemoryLayer
from codex.cognitive.context import TaskContext
from codex.cognitive.decision import DecisionMemoryProtocol
from codex.cognitive.identity import LivingIdentity
from codex.cognitive.loop import UnifiedCognitiveLoop
from codex.cognitive.presence import PresenceMonitor
from codex.cognitive.thread import ThreadFactory
from codex.cognitive.workspace import GlobalFrame
from codex.registry.model_registry import ModelRegistry


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


def test_unified_cognitive_loop_integrates_layers(tmp_path: Path) -> None:
    registry = ModelRegistry(loader=DummyLoader())
    registry.register("dummy-llm", {"type": "llm", "path": "dummy"})
    memory_layer = CausalMemoryLayer(store_path=tmp_path / "memory.jsonl")
    decision_protocol = DecisionMemoryProtocol()
    presence_monitor = PresenceMonitor()
    tracer = Tracer()
    identity = LivingIdentity()
    thread_factory = ThreadFactory()

    loop = UnifiedCognitiveLoop(
        registry=registry,
        memory_layer=memory_layer,
        decision_protocol=decision_protocol,
        presence_monitor=presence_monitor,
        tracer=tracer,
        identity=identity,
        thread_factory=thread_factory,
    )

    ctx = TaskContext(
        task_type="chat",
        input_payload={"prompt": "hello"},
        constraints={},
        candidates=["dummy-llm"],
    )
    before_identity = identity.snapshot()

    result = loop.run_task(ctx)

    assert decision_protocol.records
    assert memory_layer.store.load_all()
    assert result.state_after == presence_monitor.current_state

    thread = thread_factory.get_thread(result.thread_id)
    assert thread.events
    assert thread.events[-1].decision_record_id == result.decision_record_id
    assert thread.events[-1].memory_record_id == result.memory_record_id

    after_identity = identity.snapshot()
    assert after_identity != before_identity
    assert "dummy-llm" in after_identity["preferences"]


def test_unified_cognitive_loop_emits_global_frame(tmp_path: Path) -> None:
    registry = ModelRegistry(loader=DummyLoader())
    registry.register("dummy-llm", {"type": "llm", "path": "dummy"})
    memory_layer = CausalMemoryLayer(store_path=tmp_path / "memory.jsonl")
    decision_protocol = DecisionMemoryProtocol()
    presence_monitor = PresenceMonitor()
    tracer = Tracer()
    identity = LivingIdentity()
    thread_factory = ThreadFactory()

    loop = UnifiedCognitiveLoop(
        registry=registry,
        memory_layer=memory_layer,
        decision_protocol=decision_protocol,
        presence_monitor=presence_monitor,
        tracer=tracer,
        identity=identity,
        thread_factory=thread_factory,
    )

    received_frames = []

    def _capture_global(frame):
        from codex.cognitive.workspace import GlobalFrame

        if isinstance(frame, GlobalFrame):
            received_frames.append(frame)

    loop.workspace_bus.subscribe(_capture_global)

    ctx = TaskContext(
        task_type="chat",
        input_payload={"prompt": "hello"},
        constraints={},
        candidates=["dummy-llm"],
    )

    result = loop.run_task(ctx)

    assert loop.workspace_bus.frames
    received_frame = next(
        frame
        for frame in reversed(loop.workspace_bus.frames)
        if isinstance(frame, GlobalFrame)
    )
    assert received_frame.task_type == ctx.task_type
    assert received_frame.thread_id == result.thread_id
    assert received_frame.system_state == result.state_after
    assert received_frame.decision["choice"] == result.decision.choice
    assert received_frame.memory_refs["decision_record_id"] == result.decision_record_id
    assert received_frame.memory_refs["memory_record_id"] == result.memory_record_id
    # Note: narrative_refs may be added asynchronously, skip equality check on full frame
