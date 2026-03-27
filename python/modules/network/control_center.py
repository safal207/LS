from __future__ import annotations

from typing import Any

from .goal_vector import GoalVectorBuilder
from .models import NetworkExecutionPlan
from .need_profile import NeedProfiler
from .observer import NetworkObserver
from .orientation_center import OrientationCenter


class NetworkControlCenter:
    """Single top-level orchestrator for observer-driven network planning."""

    def __init__(
        self,
        *,
        orientation_center: OrientationCenter | None = None,
        observer_core: NetworkObserver | None = None,
        need_profiler: NeedProfiler | None = None,
        goal_vector_builder: GoalVectorBuilder | None = None,
    ) -> None:
        self.orientation_center = orientation_center or OrientationCenter()
        self.observer_core = observer_core or NetworkObserver()
        self.need_profiler = need_profiler or NeedProfiler()
        self.goal_vector_builder = goal_vector_builder or GoalVectorBuilder()

    def create_plan(
        self,
        item: dict[str, Any],
        *,
        thread_context: str | None = None,
        intent: str | None = None,
        why_tag: str | None = None,
    ) -> NetworkExecutionPlan:
        observer_report = self.observer_core.evaluate().to_dict() if self.observer_core is not None else None
        graph_decision = None
        if getattr(self.orientation_center, "graph_runtime", None) is not None:
            try:
                graph_decision_obj = self.orientation_center.graph_runtime.process(item, thread_context=thread_context)
                graph_decision = graph_decision_obj.to_dict()
            except Exception:
                graph_decision = None
        need_profile = self.need_profiler.profile(
            item,
            observer_report=observer_report,
            graph_decision=graph_decision,
        ).to_dict()
        goal_vector = self.goal_vector_builder.build(
            item,
            need_profile=need_profile,
            intent=intent,
            why_tag=why_tag,
        ).to_dict()
        plan = self.orientation_center.decide(
            item,
            thread_context=thread_context,
            intent=intent,
            why_tag=why_tag,
            observer_report=observer_report,
            goal_vector=goal_vector,
        )
        plan.need_profile = need_profile
        plan.goal_vector = goal_vector
        if need_profile["route_bias"] == "cheap_or_reuse" and plan.route_key and plan.route_key.startswith("full_run>"):
            if "local" in plan.route_key:
                plan.confidence = max(plan.confidence, 0.72)
        return plan
