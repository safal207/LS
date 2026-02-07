from __future__ import annotations

from codex.capu.tracer import Tracer
from codex.causal_memory.layer import CausalMemoryLayer
from codex.registry.model_registry import build_default_registry

from .decision import DecisionMemoryProtocol
from .identity import LivingIdentity
from .loop import UnifiedCognitiveLoop
from .presence import PresenceMonitor
from .thread import ThreadFactory


def build_default_loop() -> UnifiedCognitiveLoop:
    registry = build_default_registry()
    memory_layer = CausalMemoryLayer()
    decision_protocol = DecisionMemoryProtocol()
    presence_monitor = PresenceMonitor()
    tracer = Tracer()
    identity = LivingIdentity()
    thread_factory = ThreadFactory()
    return UnifiedCognitiveLoop(
        registry=registry,
        memory_layer=memory_layer,
        decision_protocol=decision_protocol,
        presence_monitor=presence_monitor,
        tracer=tracer,
        identity=identity,
        thread_factory=thread_factory,
    )
