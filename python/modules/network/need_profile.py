from __future__ import annotations

from typing import Any

from .models import NeedProfile


class NeedProfiler:
    """Builds a lightweight need profile for the current question."""

    def profile(
        self,
        item: dict[str, Any],
        *,
        observer_report: dict[str, Any] | None = None,
        graph_decision: dict[str, Any] | None = None,
    ) -> NeedProfile:
        text = str(item.get("text", "") or "")
        text_lower = text.lower()
        urgency = 0.45
        if "срочно" in text_lower or "быстро" in text_lower:
            urgency = 0.9
        elif "коротко" in text_lower or "в двух словах" in text_lower:
            urgency = 0.72

        similarity = float((graph_decision or {}).get("similarity") or 0.0)
        novelty = round(max(0.0, 1.0 - similarity), 4)
        memory_gap = round(0.0 if (graph_decision or {}).get("mode") == "reuse" else max(0.0, 1.0 - similarity), 4)

        observer_status = str((observer_report or {}).get("status") or "")
        uncertainty = 0.35
        if observer_status == "watch":
            uncertainty = 0.58
        elif observer_status == "intervene":
            uncertainty = 0.82

        compute_budget = 0.75
        if urgency >= 0.85:
            compute_budget = 0.4
        elif memory_gap <= 0.1:
            compute_budget = 0.3
        elif uncertainty >= 0.75:
            compute_budget = 0.9

        if urgency >= 0.85 and compute_budget <= 0.45:
            priority = "fast_response"
            route_bias = "cheap_or_reuse"
        elif uncertainty >= 0.75 or observer_status == "intervene":
            priority = "safe_correction"
            route_bias = "explore_and_verify"
        elif novelty >= 0.7:
            priority = "deep_reasoning"
            route_bias = "cooperative"
        else:
            priority = "balanced"
            route_bias = "adaptive"

        return NeedProfile(
            urgency=round(urgency, 4),
            novelty=novelty,
            uncertainty=round(uncertainty, 4),
            memory_gap=memory_gap,
            compute_budget=round(compute_budget, 4),
            priority=priority,
            route_bias=route_bias,
        )
