from __future__ import annotations

from modules.agent.counterfactual_engine import CounterfactualEngine


def test_generate_counterfactuals_from_observed_actions() -> None:
    engine = CounterfactualEngine(
        {
            "causal_edges": [
                {"cause": "tool_use", "effect": "high_quality_answer", "confidence": 0.73},
                {"cause": "structured_reasoning", "effect": "higher_user_satisfaction", "confidence": 0.65},
            ]
        }
    )
    events = [
        {"type": "decision", "value": "answer_directly"},
        {"type": "action", "value": "no_tool"},
        {"type": "outcome", "value": "low_quality_answer"},
    ]

    scenarios = engine.generate_counterfactuals(events)

    assert scenarios
    assert scenarios[0]["alternative_action"] == "tool_use"
    assert scenarios[0]["predicted_outcome"] == "high_quality_answer"
    assert scenarios[0]["confidence"] == 0.73


def test_simulate_outcome_selects_best_confidence_edge() -> None:
    engine = CounterfactualEngine(
        {
            "state": {
                "causal_edges": [
                    {"cause": "tool_use", "effect": "medium_quality_answer", "confidence": 0.41},
                    {"cause": "tool_use", "effect": "high_quality_answer", "confidence": 0.73},
                ]
            }
        }
    )

    prediction = engine.simulate_outcome("tool_use")

    assert prediction == {"predicted_outcome": "high_quality_answer", "confidence": 0.73}


def test_suggest_better_action_returns_best_alternative() -> None:
    engine = CounterfactualEngine(
        {
            "causal_edges": [
                {"cause": "structured_reasoning", "effect": "higher_user_satisfaction", "confidence": 0.65},
                {"cause": "retrieve_context", "effect": "better_grounded_answer", "confidence": 0.61},
                {"cause": "tool_use", "effect": "high_quality_answer", "confidence": 0.73},
            ]
        }
    )

    best = engine.suggest_better_action(
        [
            {"type": "decision", "value": "answer_directly"},
            {"type": "action", "value": "no_tool"},
        ]
    )

    assert best == {
        "recommended_action": "tool_use",
        "expected_outcome": "high_quality_answer",
        "confidence": 0.73,
    }
