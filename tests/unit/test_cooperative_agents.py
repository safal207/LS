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


def test_inner_agents_publish_outputs(tmp_path: Path) -> None:
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

    assert loop._on_global_frame in loop.workspace_bus.listeners
    assert len(loop.agent_registry.agents) >= 4

    ctx = TaskContext(
        task_type="chat",
        input_payload={"prompt": "hello"},
        constraints={},
        candidates=["dummy-llm"],
    )

    loop.run_task(ctx)

    global_frames = [
        frame for frame in loop.workspace_bus.frames if isinstance(frame, GlobalFrame)
    ]
    assert global_frames
    frame = global_frames[-1]

    agent_outputs = [
        item
        for item in loop.workspace_bus.frames
        if isinstance(item, dict) and item.get("agent")
    ]
    assert agent_outputs

    outputs_by_agent = {item["agent"]: item for item in agent_outputs}
    assert outputs_by_agent["analyst"]["insight"] == f"decision:{frame.decision['choice']}"
    assert outputs_by_agent["stabilizer"]["recommendation"] in ("normal", "reduce_load")
    assert outputs_by_agent["predictor"]["predicted_state"] in (
        "stable",
        "overload",
        "fragmented",
    )
    expected_merit = sum(frame.merit_scores.values()) / len(frame.merit_scores)
    assert outputs_by_agent["integrator"]["integrated_merit"] == expected_merit
