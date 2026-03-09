"""Observability helpers for replay and trend analysis."""

from __future__ import annotations

from typing import Any, Dict, List


class DecisionObservability:
    """Compute replay views and rolling trend metrics from cognitive state."""

    def __init__(self, cognitive_state: Dict[str, Any]):
        self.cognitive_state = cognitive_state

    def get_session_replay(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the latest decision records in chronological order."""
        action_log = self.cognitive_state.get("action_log", [])
        if not isinstance(action_log, list):
            return []

        replay = action_log[-max(1, limit) :]
        return [
            {
                "timestamp": item.get("timestamp"),
                "recommended_action": item.get("recommended_action"),
                "predicted_outcome": item.get("predicted_outcome"),
                "actual_outcome": item.get("actual_outcome"),
                "success": item.get("success"),
                "fallback_reason": item.get("fallback_reason"),
            }
            for item in replay
            if isinstance(item, dict)
        ]



    def get_failure_clusters(self, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Return top failure clusters by fallback_reason and tool errors."""
        action_log = self.cognitive_state.get("action_log", [])
        fallback_counts: Dict[str, int] = {}
        tool_error_counts: Dict[str, int] = {}

        if not isinstance(action_log, list):
            return {"fallback_reason": [], "tool_execution.error": []}

        for item in action_log:
            if not isinstance(item, dict):
                continue
            fallback_reason = item.get("fallback_reason")
            if fallback_reason:
                key = str(fallback_reason)
                fallback_counts[key] = fallback_counts.get(key, 0) + 1

            tool_execution = item.get("tool_execution")
            if isinstance(tool_execution, dict):
                tool_error = tool_execution.get("error")
                if tool_error:
                    key = str(tool_error)
                    tool_error_counts[key] = tool_error_counts.get(key, 0) + 1

        top_fallback = sorted(fallback_counts.items(), key=lambda x: x[1], reverse=True)[: max(1, limit)]
        top_tool_errors = sorted(tool_error_counts.items(), key=lambda x: x[1], reverse=True)[: max(1, limit)]

        return {
            "fallback_reason": [{"key": k, "count": v} for k, v in top_fallback],
            "tool_execution.error": [{"key": k, "count": v} for k, v in top_tool_errors],
        }


    def get_trend_summary(self, window: int = 20) -> Dict[str, Any]:
        """Compute rolling success/calibration/fallback trends over recent decisions."""
        replay = self.get_session_replay(limit=window)
        total = len(replay)
        if total == 0:
            return {
                "window": window,
                "decision_count": 0,
                "success_rate": 0.0,
                "calibration_error": 0.0,
                "fallback_rate": 0.0,
                "tool_kpi": {"timeout_rate": 0.0, "circuit_open_rate": 0.0, "tool_error_rate": 0.0},
                "top_failure_clusters": {"fallback_reason": [], "tool_execution.error": []},
            }

        success_count = sum(1 for x in replay if x.get("success") is True)
        fallback_count = sum(1 for x in replay if x.get("fallback_reason") is not None)

        calibration_errors: List[float] = []
        timeout_count = 0
        circuit_open_count = 0
        tool_error_count = 0

        for item in self.cognitive_state.get("action_log", [])[-total:]:
            if not isinstance(item, dict):
                continue
            confidence = float(item.get("calibrated_confidence", item.get("confidence", 0.0)) or 0.0)
            success = 1.0 if item.get("success") is True else 0.0
            calibration_errors.append(abs(confidence - success))

            tool_execution = item.get("tool_execution")
            if not isinstance(tool_execution, dict):
                continue
            status = str(tool_execution.get("status", ""))
            error_message = str(tool_execution.get("error", ""))
            if "timeout" in error_message.lower():
                timeout_count += 1
            if status == "circuit_open":
                circuit_open_count += 1
            if status == "error" or bool(error_message):
                tool_error_count += 1

        tool_kpi = {
            "timeout_rate": timeout_count / total,
            "circuit_open_rate": circuit_open_count / total,
            "tool_error_rate": tool_error_count / total,
        }

        return {
            "window": window,
            "decision_count": total,
            "success_rate": success_count / total,
            "calibration_error": (sum(calibration_errors) / len(calibration_errors)) if calibration_errors else 0.0,
            "fallback_rate": fallback_count / total,
            "tool_kpi": tool_kpi,
            "top_failure_clusters": self.get_failure_clusters(),
        }
