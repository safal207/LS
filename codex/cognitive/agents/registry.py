from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .base import InnerAgent


@dataclass
class AgentRegistry:
    agents: List[InnerAgent] = field(default_factory=list)

    def register(self, agent: InnerAgent) -> None:
        self.agents.append(agent)

    def process_frame(self, frame: Dict[str, Any]) -> List[Dict[str, Any]]:
        outputs = []
        for agent in self.agents:
            outputs.append(agent.process(frame))
        return outputs
