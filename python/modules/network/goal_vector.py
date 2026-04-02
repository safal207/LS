# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .models import GoalVector


class GoalVectorBuilder:
    """Derives the target answer profile for the current question."""

    def build(
        self,
        item: dict[str, Any],
        *,
        need_profile: dict[str, Any] | None = None,
        intent: str | None = None,
        why_tag: str | None = None,
    ) -> GoalVector:
        text = str(item.get("text", "") or "")
        text_lower = text.lower()
        need_profile = need_profile or {}
        priority = str(need_profile.get("priority") or "balanced")
        route_bias = str(need_profile.get("route_bias") or "adaptive")

        target_relevance = 0.72
        target_thread_alignment = 0.70
        target_hallucination_max = 0.28
        target_latency_ms = 9000.0
        style = "balanced"
        strategy_bias = "adaptive"

        if priority == "fast_response":
            target_latency_ms = 4500.0
            style = "concise"
            strategy_bias = "speed_first"
            target_thread_alignment = 0.64
        elif priority == "safe_correction":
            target_hallucination_max = 0.15
            target_relevance = 0.78
            target_thread_alignment = 0.78
            target_latency_ms = 12000.0
            style = "careful"
            strategy_bias = "verify_first"
        elif priority == "deep_reasoning":
            target_relevance = 0.82
            target_thread_alignment = 0.76
            target_latency_ms = 14000.0
            style = "structured"
            strategy_bias = "cooperative_reasoning"

        if "коротко" in text_lower or "в двух словах" in text_lower:
            style = "concise"
            target_latency_ms = min(target_latency_ms, 5000.0)
        if "без выдуманных" in text_lower or "без фантазии" in text_lower:
            target_hallucination_max = min(target_hallucination_max, 0.12)
            strategy_bias = "grounded"
        if intent == "technical_reasoning" or (why_tag and "reason" in why_tag):
            target_relevance = max(target_relevance, 0.8)
            target_thread_alignment = max(target_thread_alignment, 0.74)
        if route_bias == "cheap_or_reuse":
            target_latency_ms = min(target_latency_ms, 5500.0)

        return GoalVector(
            target_relevance=round(target_relevance, 4),
            target_thread_alignment=round(target_thread_alignment, 4),
            target_hallucination_max=round(target_hallucination_max, 4),
            target_latency_ms=round(target_latency_ms, 2),
            style=style,
            strategy_bias=strategy_bias,
        )
