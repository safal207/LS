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


def test_workspace_layer_publishes_global_frame(tmp_path: Path) -> None:
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

    captured = []

    def _capture_global(frame):
        from codex.cognitive.workspace import GlobalFrame

        if isinstance(frame, GlobalFrame):
            captured.append(frame)

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
    # Note: narrative_refs may be added asynchronously, check key fields only
    assert received_frame.thread_id == result.thread_id
    assert received_frame.task_type == ctx.task_type
    assert received_frame.memory_refs["memory_record_id"] == result.memory_record_id

    aggregated = loop.aggregator.aggregate(
        self_model=received_frame.self_model,
        affective=received_frame.affective,
        identity=received_frame.identity,
        capu=received_frame.capu_features,
        decision=received_frame.decision,
        causal=received_frame.memory_refs,
        state=received_frame.system_state,
    )
    expected_scores = loop.merit_engine.score(aggregated)
    assert received_frame.merit_scores == expected_scores
