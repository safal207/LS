from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from network import NeedProfiler  # noqa: E402


def test_need_profiler_prefers_fast_response_for_urgent_prompt() -> None:
    profile = NeedProfiler().profile(
        {"text": "Срочно и коротко: почему вы выбрали этот стек?"},
        observer_report={"status": "stable"},
        graph_decision={"mode": "full_run", "similarity": 0.1},
    )

    assert profile.priority == "fast_response"
    assert profile.route_bias == "cheap_or_reuse"


def test_need_profiler_prefers_safe_correction_on_intervention() -> None:
    profile = NeedProfiler().profile(
        {"text": "Почему вы выбрали этот стек?"},
        observer_report={"status": "intervene"},
        graph_decision={"mode": "full_run", "similarity": 0.2},
    )

    assert profile.priority == "safe_correction"
    assert profile.route_bias == "explore_and_verify"
