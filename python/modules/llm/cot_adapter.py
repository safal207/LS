from __future__ import annotations

import logging
from typing import Any, Dict

from hexagon_core.belief.lifecycle import BeliefLifecycleManager
from hexagon_core.causal.graph import CausalGraph
from hexagon_core.cot.core import COTCore
from hexagon_core.mission.state import MissionState
from llm.temporal import TemporalContext

logger = logging.getLogger("COTAdapter")


class COTAdapter:
    """
    Minimal adapter to run COTCore prior to LLM generation.
    This keeps prompt behavior unchanged while allowing opt-in reasoning hooks.
    """

    def __init__(self, temporal: TemporalContext | None = None, temporal_enabled: bool = True) -> None:
        self.lifecycle = BeliefLifecycleManager()
        self.causal_graph = CausalGraph()
        self.mission = MissionState()
        self.core = COTCore(self.lifecycle, self.causal_graph, self.mission)
        if temporal_enabled:
            self.temporal = temporal or TemporalContext()
        else:
            self.temporal = None

    def process(self, question: str, prompt: str) -> str:
        try:
            if self.temporal:
                self.temporal.transition("thinking")
            self.lifecycle.register_belief(question, metadata={"source": "llm_prompt"})
            self.core.run_cot_cycle(force=False)
            if self.temporal:
                self.temporal.transition("responding")
        except Exception as exc:
            logger.warning(f"COTAdapter error: {exc}")
        return prompt

    def get_summary(self) -> Dict[str, Any]:
        return self.mission.get_summary()
