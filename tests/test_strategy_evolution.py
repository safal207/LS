from agent.strategy_evolution import StrategyEvolutionEngine


def test_discover_best_strategies_orders_by_outcome_and_confidence():
    engine = StrategyEvolutionEngine({})

    strategies = engine.discover_best_strategies(
        [
            {"action": "a", "predicted_outcome": 0.7, "confidence": 0.9, "evidence_count": 8},
            {"action": "b", "predicted_outcome": 0.9, "confidence": 0.6, "evidence_count": 8},
            {"action": "c", "predicted_outcome": 0.9, "confidence": 0.8, "evidence_count": 8},
        ]
    )

    assert [item["action"] for item in strategies] == ["c", "b", "a"]


def test_discover_best_strategies_filters_cognitive_warnings():
    engine = StrategyEvolutionEngine({})

    strategies = engine.discover_best_strategies(
        [
            {
                "action": "unsafe_high_confidence",
                "predicted_outcome": 0.95,
                "confidence": 0.95,
                "evidence_count": 1,
            },
            {
                "action": "safe_strategy",
                "predicted_outcome": 0.8,
                "confidence": 0.7,
                "evidence_count": 7,
            },
        ]
    )

    assert [item["action"] for item in strategies] == ["safe_strategy"]


def test_store_as_policies_writes_to_cognitive_state():
    state = {}
    engine = StrategyEvolutionEngine(state)

    policies = engine.store_as_policies(
        [
            {
                "action": "parallel_tooling",
                "situation": {"task": "analysis"},
                "predicted_outcome": 0.88,
                "confidence": 0.82,
            }
        ]
    )

    assert "policies" in state
    assert policies == state["policies"]
    assert state["policies"][0]["action"] == "parallel_tooling"


def test_suggest_policy_returns_best_match_for_situation():
    state = {
        "policies": [
            {
                "action": "general_strategy",
                "situation": {"task": "coding"},
                "predicted_outcome": 0.85,
                "confidence": 0.8,
            },
            {
                "action": "exact_strategy",
                "situation": {"task": "coding", "urgency": "high"},
                "predicted_outcome": 0.83,
                "confidence": 0.79,
            },
        ]
    }
    engine = StrategyEvolutionEngine(state)

    suggested = engine.suggest_policy({"task": "coding", "urgency": "high", "user": "internal"})

    assert suggested["action"] == "exact_strategy"
