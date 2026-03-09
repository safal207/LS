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

    def compare_to_baseline(self, candidate: Dict[str, Any], baseline: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Compare candidate simulation KPI report against baseline."""
        baseline_report = baseline or self.cognitive_state.get("baseline_simulation_report", {})
        if not isinstance(baseline_report, dict) or not baseline_report:
            baseline_report = {
                "success_rate": 0.0,
                "prediction_accuracy": 0.0,
                "average_value": 0.0,
            }

        deltas = {
            "success_rate_delta": float(candidate.get("success_rate", 0.0) or 0.0)
            - float(baseline_report.get("success_rate", 0.0) or 0.0),
            "prediction_accuracy_delta": float(candidate.get("prediction_accuracy", 0.0) or 0.0)
            - float(baseline_report.get("prediction_accuracy", 0.0) or 0.0),
            "average_value_delta": float(candidate.get("average_value", 0.0) or 0.0)
            - float(baseline_report.get("average_value", 0.0) or 0.0),
        }

        comparison = {
            "baseline": baseline_report,
            "candidate": candidate,
            "deltas": deltas,
            "is_non_regression": all(v >= 0 for v in deltas.values()),
        }
        self.cognitive_state["simulation_comparison"] = comparison
        return comparison

    def update_baseline(self, report: Dict[str, Any]) -> None:
        """Persist a simulation report as new baseline."""
        self.cognitive_state["baseline_simulation_report"] = {
            "success_rate": float(report.get("success_rate", 0.0) or 0.0),
            "prediction_accuracy": float(report.get("prediction_accuracy", 0.0) or 0.0),
            "average_value": float(report.get("average_value", 0.0) or 0.0),
        }
