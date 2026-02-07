from __future__ import annotations

from pathlib import Path

from codex.capu.tracer import Tracer
from codex.causal_memory.layer import CausalMemoryLayer
from codex.cognitive.context import TaskContext
from codex.cognitive.decision import DecisionMemoryProtocol
from codex.cognitive.identity import LivingIdentity
from codex.cognitive.loop import UnifiedCognitiveLoop
from codex.cognitive.narrative import NarrativeEvent
from codex.cognitive.presence import PresenceMonitor
from codex.cognitive.thread import ThreadFactory
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


def test_narrative_event_published_from_agent_outputs(tmp_path: Path) -> None:
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

    loop.run_task(ctx)

    narrative = next(
        frame
        for frame in reversed(loop.workspace_bus.frames)
        if isinstance(frame, NarrativeEvent)
    )

    assert narrative.source_frame["decision"]["choice"] == "dummy-llm"
    assert "System is in state" in narrative.text
    assert "Selected model 'dummy-llm'" in narrative.text
    assert "Prediction:" in narrative.text
    assert "Stabilizer suggests:" in narrative.text


def test_narrative_timeline_tracks_recent_events(tmp_path: Path) -> None:
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

    loop.run_task(ctx)

    timeline = loop.narrative_memory.timeline(limit=5)
    assert timeline
    entry = timeline[-1]
    assert entry["decision_choice"] == "dummy-llm"
    assert entry["task_type"] == "chat"
