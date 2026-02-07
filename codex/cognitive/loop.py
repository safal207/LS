from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from codex.capu.features import extract_llm_features, extract_stt_features
from codex.capu.tracer import Tracer
from codex.causal_memory.layer import CausalMemoryLayer
from codex.causal_memory.store import MemoryRecord
from codex.registry.model_registry import ModelRegistry

from .agents import (
    AgentRegistry,
    AnalystAgent,
    IntegratorAgent,
    PredictorAgent,
    StabilizerAgent,
)
from .context import DecisionContext, LoopContext, TaskContext
from .decision import DecisionMemoryProtocol
from .identity import LivingIdentity
from .narrative import NarrativeGenerator
from .presence import PresenceMonitor
from .thread import ThreadFactory
from .workspace import GlobalFrame, MeritEngine, WorkspaceAggregator, WorkspaceBus


@dataclass
class SelectionInput:
    candidates: List[str]
    task_type: str
    constraints: Dict[str, Any]
    state: str


@dataclass
class Selector:
    causal_memory: CausalMemoryLayer
    decision_protocol: DecisionMemoryProtocol

    def select(self, selection_input: SelectionInput, identity: LivingIdentity) -> DecisionContext:
        candidates = list(selection_input.candidates)
        reasons: List[str] = []

        if identity.preferences:
            preferred = sorted(identity.preferences, key=identity.preferences.get, reverse=True)
            for model in preferred:
                if model in candidates:
                    reasons.append(f"preferred:{model}")
                    candidates.remove(model)
                    candidates.insert(0, model)
                    break

        if identity.aversions:
            for model in list(candidates):
                if model in identity.aversions and len(candidates) > 1:
                    candidates.remove(model)
                    reasons.append(f"avoided:{model}")

        causal_recommendations = self.causal_memory.engine.recommend(
            candidates, context=selection_input.constraints
        )
        if causal_recommendations:
            top = causal_recommendations[0]
            if top in candidates:
                candidates.remove(top)
                candidates.insert(0, top)
                reasons.append(f"causal:{top}")

        if candidates:
            best = max(candidates, key=lambda m: self.decision_protocol.success_rate(m))
            if best in candidates:
                candidates.remove(best)
                candidates.insert(0, best)
                reasons.append(f"dmp:{best}")

        if not candidates:
            return DecisionContext(choice="", alternatives=[], reasons=["no_candidates_available"])

        choice = candidates[0]
        alternatives = candidates[1:]
        return DecisionContext(choice=choice, alternatives=alternatives, reasons=reasons or ["default"])


@dataclass
class UnifiedCognitiveLoop:
    registry: ModelRegistry
    memory_layer: CausalMemoryLayer
    decision_protocol: DecisionMemoryProtocol
    presence_monitor: PresenceMonitor
    tracer: Tracer
    identity: LivingIdentity
    thread_factory: ThreadFactory

    selector: Selector | None = None
    capu_history: List[Dict[str, float]] = field(default_factory=list)

    # Global Workspace Layer
    aggregator: WorkspaceAggregator = field(default_factory=WorkspaceAggregator)
    merit_engine: MeritEngine = field(default_factory=MeritEngine)
    workspace_bus: WorkspaceBus = field(default_factory=WorkspaceBus)
    agent_registry: AgentRegistry = field(default_factory=AgentRegistry)
    narrative_generator: NarrativeGenerator | None = None

    def __post_init__(self) -> None:
        if not self.agent_registry.agents:
            self.agent_registry.register(AnalystAgent(name="analyst"))
            self.agent_registry.register(StabilizerAgent(name="stabilizer"))
            self.agent_registry.register(PredictorAgent(name="predictor"))
            self.agent_registry.register(IntegratorAgent(name="integrator"))
        self.narrative_generator = self.narrative_generator or NarrativeGenerator()
        self.workspace_bus.subscribe(self._on_global_frame)
        self.workspace_bus.subscribe(self._on_agent_output)

    def run_task(self, ctx: TaskContext) -> LoopContext:
        identity_snapshot = self.identity.snapshot()
        state_before = self.presence_monitor.current_state

        selection_input = SelectionInput(
            candidates=ctx.candidates or self.registry.list_models(),
            task_type=ctx.task_type,
            constraints=ctx.constraints,
            state=state_before,
        )
        selector = self.selector or Selector(self.memory_layer, self.decision_protocol)
        decision_context = selector.select(selection_input, self.identity)

        if not decision_context.choice:
            raise ValueError(f"No model selected for task {ctx.task_type}. Reasons: {decision_context.reasons}")

        thread_id = ctx.input_payload.get("thread_id")
        thread = self.thread_factory.get_thread(thread_id)

        model_name = decision_context.choice
        model_config = self.registry.info(model_name)
        model_type = model_config.get("type", "custom")
        model = self.registry.load(model_name)

        start = time.perf_counter()
        model_output, capu_features = self._execute_model(model_name, model_type, model, ctx.input_payload)
        latency = time.perf_counter() - start

        metrics = {"latency_s": latency}
        hardware = self.memory_layer._collect_hardware_profile()

        memory_record = self._record_memory(
            model_name=model_name,
            model_type=model_type,
            input_payload=ctx.input_payload,
            output_payload=model_output,
            capu_features=capu_features,
            metrics=metrics,
            hardware=hardware,
        )

        state_after = self.presence_monitor.update(capu_features, metrics, hardware)

        decision_record = self.decision_protocol.record_decision(
            choice=decision_context.choice,
            alternatives=decision_context.alternatives,
            reasons=decision_context.reasons,
            consequences={"latency_s": latency, "success": memory_record.success},
            system_state_before=state_before,
            system_state_after=state_after,
            thread_id=thread.thread_id,
            success=memory_record.success,
        )

        self.identity.update_from_capu(capu_features)
        self.identity.update_from_state(state_after)
        self.identity.update_from_causal(memory_record)
        self.identity.update_from_decision(decision_record)

        thread.add_event(
            state_before=state_before,
            state_after=state_after,
            decision_record_id=decision_record.record_id,
            memory_record_id=memory_record.record_id,
            identity_snapshot=self.identity.snapshot(),
        )
        self.identity.update_from_thread(thread)

        self.capu_history.append(capu_features)

        # Build Global Workspace Frame
        identity_snapshot = self.identity.snapshot()
        self_model_snapshot = self._build_self_model(identity_snapshot, state_after)
        affective_snapshot = self._build_affective(state_after, metrics)

        aggregated = self.aggregator.aggregate(
            self_model=self_model_snapshot,
            affective=affective_snapshot,
            identity=identity_snapshot,
            capu=capu_features,
            decision=asdict(decision_context),
            causal={
                "memory_record_id": memory_record.record_id,
                "decision_record_id": decision_record.record_id,
            },
            state=state_after,
        )

        merit_scores = self.merit_engine.score(aggregated)

        frame = GlobalFrame(
            thread_id=thread.thread_id,
            task_type=ctx.task_type,
            system_state=state_after,
            self_model=aggregated["self_model"],
            affective=aggregated["affective"],
            identity=aggregated["identity"],
            capu_features=aggregated["capu"],
            decision=aggregated["decision"],
            memory_refs=aggregated["causal"],
            merit_scores=merit_scores,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.workspace_bus.publish(frame)

        return LoopContext(
            task=ctx,
            decision=decision_context,
            model_output=model_output,
            capu_features=capu_features,
            metrics=metrics,
            state_before=state_before,
            state_after=state_after,
            memory_record_id=memory_record.record_id,
            decision_record_id=decision_record.record_id,
            thread_id=thread.thread_id,
            identity_snapshot=identity_snapshot,
        )

    def _on_global_frame(self, frame: GlobalFrame) -> None:
        if not isinstance(frame, GlobalFrame):
            return
        agent_outputs = self.agent_registry.process_frame(asdict(frame))
        for output in agent_outputs:
            self.workspace_bus.publish(output)

    def _on_agent_output(self, item: Any) -> None:
        if not isinstance(item, dict) or "agent" not in item:
            return

        agent_outputs = {
            output["agent"]: output
            for output in self.workspace_bus.frames
            if isinstance(output, dict) and "agent" in output
        }
        frame = next(
            (candidate for candidate in reversed(self.workspace_bus.frames) if isinstance(candidate, GlobalFrame)),
            None,
        )
        if frame is None:
            return

        narrative = self.narrative_generator.generate(asdict(frame), agent_outputs)
        self.workspace_bus.publish(narrative)

    @staticmethod
    def _build_self_model(identity_snapshot: Dict[str, Any], state: str) -> Dict[str, Any]:
        mapping = {
            "stable": 0.0,
            "uncertain": 0.2,
            "overload": 0.4,
            "fragmented": 0.6,
        }
        fragmentation = mapping.get(state, 0.3)
        return {"fragmentation": fragmentation, "state": state, "identity": identity_snapshot}

    @staticmethod
    def _build_affective(state: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        base = {
            "stable": 1.0,
            "overload": 0.6,
            "fragmented": 0.4,
            "uncertain": 0.7,
        }
        energy = base.get(state, 0.5)
        latency = metrics.get("latency_s")
        if isinstance(latency, (int, float)) and latency > 2.0:
            energy = max(0.1, energy - 0.2)
        return {"energy": energy, "state": state}

    def _execute_model(self, model_name: str, model_type: str, model: Any, input_payload: Dict[str, Any]):
        if model_type == "stt":
            hooks, wrapped = self.tracer.start_stt_session(model_name, model)
            output = {"result": self._run_stt(wrapped, input_payload)}
            signals = self.tracer.end_stt_session(model_name)
            features = extract_stt_features(signals)
            return output, features

        hooks = self.tracer.start_llm_session(model_name, model)
        output = {"result": self._run_llm(model, input_payload)}
        signals = self.tracer.end_llm_session(model_name)
        features = extract_llm_features(signals)
        return output, features

    @staticmethod
    def _run_llm(model: Any, input_payload: Dict[str, Any]) -> Any:
        if hasattr(model, "generate"):
            return model.generate(input_payload)
        if callable(model):
            return model(input_payload)
        return {"status": "noop", "payload": input_payload}

    @staticmethod
    def _run_stt(model: Any, input_payload: Dict[str, Any]) -> Any:
        if hasattr(model, "transcribe"):
            return model.transcribe(input_payload.get("audio"))
        if callable(model):
            return model(input_payload)
        return {"status": "noop", "payload": input_payload}

    def _record_memory(
        self,
        *,
        model_name: str,
        model_type: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
        capu_features: Dict[str, float],
        metrics: Dict[str, Any],
        hardware: Dict[str, Any],
    ) -> MemoryRecord:
        return self.memory_layer.record_task(
            model=model_name,
            model_type=model_type,
            inputs=input_payload,
            outputs=output_payload,
            parameters={"capu_features": capu_features, "hardware": hardware, "metrics": metrics},
        )
