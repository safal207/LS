"""Reflection engine that analyzes recent decisions and proposes improvements."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


class ReflectionEngine:
    """Analyze recent decisions and generate bounded change proposals."""

    def __init__(self, cognitive_state: Dict[str, Any], window: int = 50):
        self.cognitive_state = cognitive_state
        self.window = window

    def generate_proposals(self, max_proposals: int = 3) -> List[Dict[str, Any]]:
        """Generate and rank up to ``max_proposals`` reflection suggestions."""
        proposals: List[Dict[str, Any]] = []

        success_drop = self._detect_success_rate_drop()
        if success_drop:
            proposals.append(success_drop)

        fallback_spike = self._detect_fallback_spike()
        if fallback_spike:
            proposals.append(fallback_spike)

        tool_error_spike = self._detect_tool_error_spike()
        if tool_error_spike:
            proposals.append(tool_error_spike)

        proposals.sort(key=lambda proposal: proposal["confidence"], reverse=True)
        return proposals[:max_proposals]

    def _detect_success_rate_drop(self) -> Dict[str, Any] | None:
        """Flag when recent success rate is materially below historical baseline."""
        history = self.cognitive_state.get("action_history", [])
        if len(history) < self.window:
            return None

        recent = history[-self.window :]
        recent_success = sum(1 for item in recent if item.get("success") is True)
        recent_total = len(recent)
        recent_rate = recent_success / recent_total if recent_total > 0 else 0.0

        stats = self.cognitive_state.get("strategy_stats", {})
        baseline_rates = [
            strategy["successes"] / strategy["attempts"] if strategy["attempts"] > 0 else 0.5
            for strategy in stats.values()
            if isinstance(strategy, dict) and strategy.get("attempts", 0) > 0
        ]
        baseline_rate = sum(baseline_rates) / len(baseline_rates) if baseline_rates else 0.5

        if recent_rate < baseline_rate * 0.7 and recent_rate < 0.6:
            return {
                "proposal_id": f"refl_success_drop_{self._utc_suffix()}",
                "change_type": "control_update",
                "target": "low_confidence_threshold",
                "proposed_value": 0.35,
                "reason": (
                    f"Success rate dropped from ~{baseline_rate:.2f} to {recent_rate:.2f} "
                    f"in the last {self.window} actions"
                ),
                "confidence": 0.82,
                "expected_gain": "+12–18%",
                "auto_apply": False,
            }
        return None

    def _detect_fallback_spike(self) -> Dict[str, Any] | None:
        """Flag when fallback usage doubled versus previous equal window."""
        action_log = self.cognitive_state.get("action_log", [])
        if len(action_log) < self.window * 2:
            return None

        recent = action_log[-self.window :]
        previous = action_log[-self.window * 2 : -self.window]

        recent_fallbacks = sum(1 for item in recent if item.get("fallback_reason") is not None)
        previous_fallbacks = sum(1 for item in previous if item.get("fallback_reason") is not None)

        recent_rate = recent_fallbacks / len(recent) if recent else 0.0
        previous_rate = previous_fallbacks / len(previous) if previous else 0.0

        if recent_rate > previous_rate * 2 and recent_rate > 0.25:
            return {
                "proposal_id": f"refl_fallback_spike_{self._utc_suffix()}",
                "change_type": "control_update",
                "target": "fallback_action",
                "proposed_value": "structured_reasoning",
                "reason": (
                    f"Fallback rate increased from {previous_rate:.2f} to {recent_rate:.2f} "
                    f"in the last {self.window} actions"
                ),
                "confidence": 0.75,
                "expected_gain": "+10–15%",
                "auto_apply": False,
            }
        return None

    def _detect_tool_error_spike(self) -> Dict[str, Any] | None:
        """Flag tool demotion candidate if one tool accumulated repeated errors."""
        errors = self.cognitive_state.get("tool_error_counts", {})
        if not errors:
            return None

        problematic_tool = None
        max_count = 0
        for action, count in errors.items():
            if isinstance(count, int) and count > max_count:
                max_count = count
                problematic_tool = action

        if max_count >= 5 and problematic_tool:
            return {
                "proposal_id": f"refl_tool_error_{self._utc_suffix()}",
                "change_type": "tool_demotion",
                "target": problematic_tool,
                "proposed_value": None,
                "reason": f"Tool '{problematic_tool}' failed {max_count} times in recent actions",
                "confidence": 0.88,
                "expected_gain": "20–30% fewer errors",
                "auto_apply": False,
            }
        return None

    @staticmethod
    def _utc_suffix() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
