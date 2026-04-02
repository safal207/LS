from __future__ import annotations

from typing import Any

from .cognitive_adequacy import CognitiveAdequacyCore
from graph.memory_store import MemoryGraphStore
from .observer import NetworkObserver
from .models import NetworkExecutionPlan


class OrientationCenter:
    """Unifies graph-memory, route selection, coalition preference, and derived modules."""

    def __init__(
        self,
        *,
        graph_runtime=None,
        path_selector=None,
        derived_module_registry=None,
        memory_store: MemoryGraphStore | None = None,
        llm_backend=None,
        adequacy_core: CognitiveAdequacyCore | None = None,
        observer_core: NetworkObserver | None = None,
        derived_min_quality: float = 0.72,
        derived_min_trust: float = 0.62,
    ) -> None:
        self.graph_runtime = graph_runtime
        self.path_selector = path_selector
        self.derived_module_registry = derived_module_registry
        self.memory_store = memory_store
        self.llm_backend = llm_backend
        self.adequacy_core = adequacy_core
        self.observer_core = observer_core
        self.derived_min_quality = derived_min_quality
        self.derived_min_trust = derived_min_trust

    def decide(
        self,
        item: dict[str, Any],
        *,
        thread_context: str | None = None,
        intent: str | None = None,
        why_tag: str | None = None,
        observer_report: dict[str, Any] | None = None,
        goal_vector: dict[str, Any] | None = None,
    ) -> NetworkExecutionPlan:
        graph_decision = None
        graph_meta = None
        resonance_signal = None
        observer_meta = observer_report
        adequacy_meta = None
        if self.graph_runtime is not None:
            graph_decision = self.graph_runtime.process(item, thread_context=thread_context)
            graph_meta = graph_decision.to_dict()
        if observer_meta is not None:
            adequacy_meta = observer_meta.get("adequacy")
        elif self.observer_core is not None:
            observer_meta = self.observer_core.evaluate().to_dict()
            adequacy_meta = observer_meta.get("adequacy")
        elif self.adequacy_core is not None:
            adequacy_meta = self.adequacy_core.evaluate().to_dict()

        if self.memory_store is None and self.graph_runtime is not None:
            runtime_store = getattr(self.graph_runtime, "store", None)
            if runtime_store is not None:
                self.memory_store = runtime_store

        resonance_units = []
        if self.memory_store is not None:
            query_text = (
                item.get("clean_text")
                or item.get("text")
                or item.get("question")
                or item.get("raw_text")
            )
            resonance_units = self.memory_store.find_relevant_units(
                intent=intent,
                why=why_tag,
                query_text=str(query_text or ""),
                top_k=3,
            )
            if resonance_units:
                top_unit = resonance_units[0]
                resonance_signal = {
                    "count": len(resonance_units),
                    "top_unit_id": top_unit.unit_id,
                    "top_intent": top_unit.intent,
                    "top_why": top_unit.why,
                    "top_resonance_score": float(top_unit.resonance_score or 0.0),
                    "top_alignment_score": float(top_unit.alignment_score or 0.0),
                }

        available_backends: list[str] = []
        if self.llm_backend is not None and hasattr(self.llm_backend, "backends"):
            available_backends = [
                name for name in ("gonka", "mimo", "cloud", "local")
                if name in getattr(self.llm_backend, "backends", {})
            ]

        adequacy_status = (adequacy_meta or {}).get("status")
        derived_min_quality = self.derived_min_quality
        derived_min_trust = self.derived_min_trust
        if adequacy_status == "watch":
            derived_min_quality = max(derived_min_quality, 0.78)
            derived_min_trust = max(derived_min_trust, 0.68)
        elif adequacy_status == "intervene":
            derived_min_quality = max(derived_min_quality, 0.85)
            derived_min_trust = max(derived_min_trust, 0.78)

        if graph_decision is not None and graph_decision.mode == "reuse":
            return NetworkExecutionPlan(
                mode="reuse",
                route_key="reuse",
                coalition_id=None,
                derived_module_id=None,
                memory_case_id=graph_decision.matched_case_id,
                reason=graph_decision.reason,
                confidence=float(graph_decision.similarity or 0.0),
                graph_decision=graph_meta,
                resonance_signal=resonance_signal,
                goal_vector=goal_vector,
                adequacy_report=adequacy_meta,
                observer_report=observer_meta,
                available_backends=available_backends,
            )

        derived_module = None
        if self.derived_module_registry is not None and available_backends:
            derived_module = self.derived_module_registry.find_best(
                available_backends=available_backends,
                domain=intent,
                task_type=why_tag,
                min_quality=derived_min_quality,
                min_trust=derived_min_trust,
            )
        if derived_module is not None:
            module_meta = derived_module.to_dict()
            return NetworkExecutionPlan(
                mode=(graph_decision.mode if graph_decision is not None else "full_run"),
                route_key=f"derived>{derived_module.module_id}",
                coalition_id=derived_module.parent_coalition_id or None,
                derived_module_id=derived_module.module_id,
                memory_case_id=(graph_decision.matched_case_id if graph_decision is not None else None),
                reason="derived-module",
                confidence=float(derived_module.trust_score or 0.0),
                selected_backend=derived_module.preferred_backend,
                graph_decision=graph_meta,
                derived_module=module_meta,
                resonance_signal=resonance_signal,
                goal_vector=goal_vector,
                adequacy_report=adequacy_meta,
                observer_report=observer_meta,
                available_backends=available_backends,
            )

        path_decision = None
        if self.path_selector is not None and graph_decision is not None and graph_decision.mode != "reuse":
            default_backend = getattr(self.llm_backend, "primary", None) if self.llm_backend is not None else None
            path_decision = self.path_selector.choose_route(
                graph_mode=graph_decision.mode,
                available_backends=available_backends,
                default_backend=default_backend,
                intent=intent,
                why_tag=why_tag,
                force_exploration=(adequacy_status == "intervene"),
                goal_style=(goal_vector or {}).get("style"),
                strategy_bias=(goal_vector or {}).get("strategy_bias"),
            )
            path_meta = path_decision.to_dict()
            coalition_id = None
            if path_decision.reason == "coalition-registry" and path_decision.route_key:
                coalition_id = path_decision.route_key.replace(">", "-")
            resonance_boost = 0.0
            reason = path_decision.reason
            confidence = float(path_decision.pheromone_weight or 0.0)
            if resonance_signal is not None:
                top_resonance = resonance_signal["top_resonance_score"]
                top_alignment = resonance_signal["top_alignment_score"]
                resonance_boost = min(0.12, (top_resonance * 0.08) + (top_alignment * 0.04))
                confidence += resonance_boost
                reason = f"{reason}+resonance-memory"
            return NetworkExecutionPlan(
                mode=graph_decision.mode,
                route_key=path_decision.route_key,
                coalition_id=coalition_id,
                derived_module_id=None,
                memory_case_id=graph_decision.matched_case_id,
                reason=reason,
                confidence=confidence,
                selected_backend=path_decision.selected_backend,
                graph_decision=graph_meta,
                path_decision=path_meta,
                resonance_signal=resonance_signal,
                goal_vector=goal_vector,
                adequacy_report=adequacy_meta,
                observer_report=observer_meta,
                available_backends=available_backends,
            )

        fallback_mode = graph_decision.mode if graph_decision is not None else "full_run"
        return NetworkExecutionPlan(
            mode=fallback_mode,
            route_key=None,
            coalition_id=None,
            derived_module_id=None,
            memory_case_id=(graph_decision.matched_case_id if graph_decision is not None else None),
            reason="orientation-fallback",
            confidence=float(graph_decision.similarity or 0.0) if graph_decision is not None else 0.0,
            graph_decision=graph_meta,
            resonance_signal=resonance_signal,
            goal_vector=goal_vector,
            adequacy_report=adequacy_meta,
            observer_report=observer_meta,
            available_backends=available_backends,
        )
