"""Operator-style API for runtime LLM routing controls."""

from __future__ import annotations

from typing import Any, Dict

from .llm_module import LanguageModel


class LLMRoutingOperatorAPI:
    """Thin API wrapper around LanguageModel routing control surface."""

    def __init__(self, model: LanguageModel):
        self.model = model

    def get_routing_snapshot(self) -> Dict[str, Any]:
        """Equivalent to GET /llm/routing."""
        return self.model.get_routing_observability()

    def post_routing_controls(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Equivalent to POST /llm/routing/controls."""
        snapshot = self.model.update_routing_controls(payload)
        return {"status": "ok", "snapshot": snapshot}

    def post_rollout_stage(self, stage: str) -> Dict[str, Any]:
        """Equivalent to POST /llm/routing/rollout with stage value."""
        snapshot = self.model.apply_rollout_stage(stage)
        return {"status": "ok", "stage": stage, "snapshot": snapshot}
