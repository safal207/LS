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
            }

        success_count = sum(1 for x in replay if x.get("success") is True)
        fallback_count = sum(1 for x in replay if x.get("fallback_reason") is not None)

        calibration_errors: List[float] = []
        for item in self.cognitive_state.get("action_log", [])[-total:]:
            if not isinstance(item, dict):
                continue
            confidence = float(item.get("calibrated_confidence", item.get("confidence", 0.0)) or 0.0)
            success = 1.0 if item.get("success") is True else 0.0
            calibration_errors.append(abs(confidence - success))

        return {
            "window": window,
            "decision_count": total,
            "success_rate": success_count / total,
            "calibration_error": (sum(calibration_errors) / len(calibration_errors)) if calibration_errors else 0.0,
            "fallback_rate": fallback_count / total,
        }
