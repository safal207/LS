"""Simulation utilities for KPI-based strategy benchmarking."""

from __future__ import annotations

from typing import Any, Dict, List


class StrategySimulationEngine:
    """Run strategy simulations and compute KPI summaries."""

    def __init__(self, cognitive_state: Dict[str, Any]):
        self.cognitive_state = cognitive_state

    def run(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute simulation scenarios and aggregate KPI metrics."""
        results: List[Dict[str, Any]] = []

        for scenario in scenarios:
            action = scenario.get("action")
            predicted_outcome = scenario.get("predicted_outcome")
            actual_outcome = scenario.get("actual_outcome")
            success = bool(scenario.get("success", False))
            value = float(scenario.get("outcome_value", 0.0) or 0.0)

            results.append(
                {
                    "action": action,
                    "predicted_outcome": predicted_outcome,
                    "actual_outcome": actual_outcome,
                    "success": success,
                    "outcome_value": value,
                    "prediction_match": predicted_outcome == actual_outcome,
                }
            )

        total = len(results)
        if total == 0:
            report = {
                "scenario_count": 0,
                "success_rate": 0.0,
                "prediction_accuracy": 0.0,
                "total_value": 0.0,
                "average_value": 0.0,
                "results": [],
            }
            self.cognitive_state["simulation_report"] = report
            return report

        success_count = sum(1 for r in results if r["success"])
        prediction_match_count = sum(1 for r in results if r["prediction_match"])
        total_value = sum(r["outcome_value"] for r in results)

        report = {
            "scenario_count": total,
            "success_rate": success_count / total,
            "prediction_accuracy": prediction_match_count / total,
            "total_value": total_value,
            "average_value": total_value / total,
            "results": results,
        }
        self.cognitive_state["simulation_report"] = report
        return report
