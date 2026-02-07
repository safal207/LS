from __future__ import annotations

import logging
from typing import Any, Dict

from python.modules.hexagon_core.belief.lifecycle import BeliefLifecycleManager
from python.modules.hexagon_core.causal.graph import CausalGraph
from python.modules.hexagon_core.cot.core import COTCore
from python.modules.hexagon_core.mission.state import MissionState

logger = logging.getLogger("COTAdapter")


class COTAdapter:
    """
    Minimal adapter to run COTCore prior to LLM generation.
    This keeps prompt behavior unchanged while allowing opt-in reasoning hooks.
    """

    def __init__(self) -> None:
        self.lifecycle = BeliefLifecycleManager()
        self.causal_graph = CausalGraph()
        self.mission = MissionState()
        self.core = COTCore(self.lifecycle, self.causal_graph, self.mission)

    def process(self, question: str, prompt: str) -> str:
        try:
            self.lifecycle.register_belief(question, metadata={"source": "llm_prompt"})
            self.core.run_cot_cycle(force=False)
        except Exception as exc:
            logger.warning(f"COTAdapter error: {exc}")
        return prompt

    def get_summary(self) -> Dict[str, Any]:
        return self.mission.get_summary()
