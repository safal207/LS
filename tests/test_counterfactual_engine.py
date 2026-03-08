from agent.counterfactual_engine import CounterfactualEngine


def test_generate_counterfactuals() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "high_quality_answer", "confidence": 0.75},
            {"cause": "structured_reasoning", "effect": "better_explanation", "confidence": 0.65},
        ]
    }
    engine = CounterfactualEngine(state)
    events = [{"type": "decision", "value": "answer_directly"}]

    counterfactuals = engine.generate_counterfactuals(events)
    assert any(c["alternative_action"] == "answer_with_tool" for c in counterfactuals)
    assert any(c["alternative_action"] == "structured_reasoning" for c in counterfactuals)


def test_simulate_outcome_returns_best_edge() -> None:
    state = {"causal_edges": [{"cause": "x", "effect": "y", "confidence": 0.9}]}
    engine = CounterfactualEngine(state)
    outcome = engine.simulate_outcome("x")
    assert outcome["predicted_outcome"] == "y"
    assert outcome["confidence"] == 0.9


def test_suggest_better_action_returns_max_confidence() -> None:
    state = {
        "causal_edges": [
            {"cause": "answer_with_tool", "effect": "o1", "confidence": 0.5},
            {"cause": "retrieve_context", "effect": "o2", "confidence": 0.8},
        ]
    }
    engine = CounterfactualEngine(state)
    events = [{"type": "decision", "value": "answer_directly"}]
    best = engine.suggest_better_action(events)
    assert best["recommended_action"] == "retrieve_context"
    assert best["expected_outcome"] == "o2"
    assert best["confidence"] == 0.8
