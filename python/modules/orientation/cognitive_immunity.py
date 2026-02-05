from __future__ import annotations

from typing import Any

from .metrics import clamp, safe_ratio


class CognitiveImmunity:
    """
    Skeleton: computes drift pressure from drift/anomaly signals.
    """

    def evaluate(self, signals: dict[str, Any] | None) -> float:
        data = signals or {}
        if "drift_pressure" in data:
            return clamp(float(data["drift_pressure"]))

        anomaly_rate = float(data.get("anomaly_rate", 0.0))
        bias_flags = float(data.get("bias_flags", 0.0))
        drift_signals = data.get("drift_signals", []) or []

        drift_avg = safe_ratio(sum(float(x) for x in drift_signals), len(drift_signals)) if drift_signals else 0.0
        bias_score = clamp(bias_flags / 10.0)

        pressure = (0.5 * anomaly_rate) + (0.3 * drift_avg) + (0.2 * bias_score)
        return clamp(pressure)
