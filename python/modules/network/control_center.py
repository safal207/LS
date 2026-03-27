from __future__ import annotations

from typing import Any

from .models import NetworkExecutionPlan
from .observer import NetworkObserver
from .orientation_center import OrientationCenter


class NetworkControlCenter:
    """Single top-level orchestrator for observer-driven network planning."""

    def __init__(
        self,
        *,
        orientation_center: OrientationCenter | None = None,
        observer_core: NetworkObserver | None = None,
    ) -> None:
        self.orientation_center = orientation_center or OrientationCenter()
        self.observer_core = observer_core or NetworkObserver()

    def create_plan(
        self,
        item: dict[str, Any],
        *,
        thread_context: str | None = None,
        intent: str | None = None,
        why_tag: str | None = None,
    ) -> NetworkExecutionPlan:
        observer_report = self.observer_core.evaluate().to_dict() if self.observer_core is not None else None
        return self.orientation_center.decide(
            item,
            thread_context=thread_context,
            intent=intent,
            why_tag=why_tag,
            observer_report=observer_report,
        )
