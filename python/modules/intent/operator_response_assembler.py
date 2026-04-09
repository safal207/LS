from __future__ import annotations

from .body_aware_copilot import BodyAwareCopilot, CopilotOutput


class OperatorResponseAssembler(BodyAwareCopilot):
    """Neutral alias for the historical BodyAwareCopilot contract."""


__all__ = ["OperatorResponseAssembler", "BodyAwareCopilot", "CopilotOutput"]
