from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from codex.capu.features import extract_llm_features, extract_stt_features
from codex.capu.tracer import Tracer
from codex.causal_memory.layer import CausalMemoryLayer
from codex.causal_memory.store import MemoryRecord
from codex.registry.model_registry import ModelRegistry

from .context import DecisionContext, LoopContext, TaskContext
from .decision import DecisionMemoryProtocol
from .identity import LivingIdentity
from .presence import PresenceMonitor
from .thread import ThreadFactory


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

        causal_recommendations = self.causal_memory.engine.recommend(candidates, context=selection_input.constraints)
        if causal_recommendations:
            top = causal_recommendations[0]
            if top in candidates:
                candidates.remove(top)
                candidates.insert(0, top)
                reasons.append(f"causal:{top}")

        if candidates:
            best = max(
                candidates,
                key=lambda model: self.decision_protocol.success_rate(model),
            )
            if best in candidates:
                candidates.remove(best)
                candidates.insert(0, best)
                reasons.append(f"dmp:{best}")

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

    def _execute_model(
        self,
        model_name: str,
        model_type: str,
        model: Any,
        input_payload: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, float]]:
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
            parameters={"capu_features": capu_features},
            hardware=hardware,
            metrics=metrics,
            success=True,
        )
