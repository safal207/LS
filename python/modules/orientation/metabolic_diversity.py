from __future__ import annotations

from typing import Any

from .metrics import clamp, safe_ratio


class MetabolicDiversity:
    """
    Skeleton: computes a diversity score from history stats.
    """

    def evaluate(self, history_stats: dict[str, Any] | None) -> float:
        stats = history_stats or {}
        if "diversity_score" in stats:
            return clamp(float(stats["diversity_score"]))
        if "entropy" in stats:
            return clamp(float(stats["entropy"]))

        unique_paths = float(stats.get("unique_paths", 0.0))
        total_paths = float(stats.get("total_paths", 0.0))
        return clamp(safe_ratio(unique_paths, total_paths))
