from __future__ import annotations

from .why_strategy import WhyStrategy, analyze_why_and_strategy


def analyze_operator_strategy(text: str) -> WhyStrategy:
    """Neutral alias for the historical why-strategy analyzer."""
    return analyze_why_and_strategy(text)


__all__ = ["WhyStrategy", "analyze_operator_strategy", "analyze_why_and_strategy"]
