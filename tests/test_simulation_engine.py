from agent.simulation_engine import StrategySimulationEngine


def test_simulation_engine_aggregates_kpis() -> None:
    state = {}
    engine = StrategySimulationEngine(state)

    report = engine.run(
        [
            {
                "action": "answer_with_tool",
                "predicted_outcome": "good",
                "actual_outcome": "good",
                "success": True,
                "outcome_value": 0.9,
            },
            {
                "action": "retrieve_context",
                "predicted_outcome": "ok",
                "actual_outcome": "bad",
                "success": False,
                "outcome_value": 0.2,
            },
        ]
    )

    assert report["scenario_count"] == 2
    assert report["success_rate"] == 0.5
    assert report["prediction_accuracy"] == 0.5
    assert report["total_value"] == 1.1
    assert state["simulation_report"]["average_value"] == 0.55


def test_simulation_engine_handles_empty_scenarios() -> None:
    state = {}
    engine = StrategySimulationEngine(state)

    report = engine.run([])

    assert report["scenario_count"] == 0
    assert report["success_rate"] == 0.0
    assert report["prediction_accuracy"] == 0.0


def test_simulation_engine_compare_to_baseline_and_promote() -> None:
    state = {}
    engine = StrategySimulationEngine(state)

    baseline = {"success_rate": 0.4, "prediction_accuracy": 0.4, "average_value": 0.3}
    candidate = {"success_rate": 0.6, "prediction_accuracy": 0.5, "average_value": 0.35}

    comparison = engine.compare_to_baseline(candidate, baseline)

    assert comparison["is_non_regression"] is True
    assert abs(comparison["deltas"]["success_rate_delta"] - 0.2) < 1e-9

    engine.update_baseline(candidate)
    assert state["baseline_simulation_report"]["success_rate"] == 0.6
