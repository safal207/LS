from __future__ import annotations

from .counterparty_profile_model import CounterpartyProfile


class OperatorProfile(CounterpartyProfile):
    """Operator-facing profile contract for live response shaping."""


__all__ = ["OperatorProfile", "CounterpartyProfile"]
