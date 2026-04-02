# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from network import GoalVectorBuilder  # noqa: E402


def test_goal_vector_prefers_careful_profile_for_safe_correction() -> None:
    vector = GoalVectorBuilder().build(
        {"text": "Почему вы выбрали этот стек? Без выдуманных цифр."},
        need_profile={"priority": "safe_correction", "route_bias": "explore_and_verify"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert vector.style == "careful"
    assert vector.target_hallucination_max <= 0.15
    assert vector.strategy_bias in {"verify_first", "grounded"}


def test_goal_vector_prefers_concise_profile_for_fast_response() -> None:
    vector = GoalVectorBuilder().build(
        {"text": "Коротко: почему вы выбрали этот стек?"},
        need_profile={"priority": "fast_response", "route_bias": "cheap_or_reuse"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert vector.style == "concise"
    assert vector.target_latency_ms <= 5000.0
