import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "agent" / "reflection_engine.py"
spec = importlib.util.spec_from_file_location("reflection_engine", MODULE_PATH)
reflection_engine = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(reflection_engine)
ReflectionEngine = reflection_engine.ReflectionEngine


def test_reflection_engine_detects_and_orders_proposals():
    cognitive_state = {
        "action_history": [{"success": False} for _ in range(50)],
        "strategy_stats": {
            "answer_with_tool": {"attempts": 10, "successes": 9},
            "retrieve_context": {"attempts": 5, "successes": 4},
        },
        "action_log": (
            [{"fallback_reason": None} for _ in range(50)]
            + [{"fallback_reason": "tool_error"} for _ in range(20)]
            + [{"fallback_reason": None} for _ in range(30)]
        ),
        "tool_error_counts": {"answer_with_tool": 7, "retrieve_context": 2},
    }

    proposals = ReflectionEngine(cognitive_state, window=50).generate_proposals(max_proposals=3)

    assert len(proposals) == 3
    assert proposals[0]["change_type"] == "tool_demotion"
    assert {proposal["target"] for proposal in proposals} == {
        "answer_with_tool",
        "low_confidence_threshold",
        "fallback_action",
    }


def test_reflection_engine_returns_empty_when_data_is_insufficient():
    cognitive_state = {
        "action_history": [{"success": True} for _ in range(10)],
        "strategy_stats": {},
        "action_log": [{"fallback_reason": None} for _ in range(10)],
        "tool_error_counts": {"retrieve_context": 1},
    }

    proposals = ReflectionEngine(cognitive_state, window=50).generate_proposals()

    assert proposals == []
