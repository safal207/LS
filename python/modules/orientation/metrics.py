"""
Shared metrics utilities for Orientation Center (Phase 13.2)
"""

from __future__ import annotations

from dataclasses import dataclass


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


@dataclass(frozen=True)
class OrientationSignals:
    diversity_score: float
    stability_score: float
    contradiction_rate: float
    drift_pressure: float
    confidence_budget: float
