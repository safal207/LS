from __future__ import annotations

from typing import Any

from .metrics import clamp


class TemporalCausality:
    """
    Skeleton: computes contradiction rate from temporal trends.
    """

    def evaluate(self, metrics: dict[str, Any] | None) -> float:
        data = metrics or {}
        if "contradiction_rate" in data:
            return clamp(float(data["contradiction_rate"]))

        short_term = float(data.get("short_term_trend", 0.0))
        long_term = float(data.get("long_term_trend", 0.0))
        return clamp(abs(short_term - long_term))
