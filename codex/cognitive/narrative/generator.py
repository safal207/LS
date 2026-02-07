from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from .base import NarrativeEvent


@dataclass
class NarrativeGenerator:
    def generate(self, frame: Dict[str, Any], agent_outputs: Dict[str, Any]) -> NarrativeEvent:
        state = frame.get("system_state")
        decision = frame.get("decision", {})
        choice = decision.get("choice", "unknown")
        reasons = decision.get("reasons", [])

        summary = (
            f"System is in state '{state}'. "
            f"Selected model '{choice}' due to {', '.join(reasons)}. "
            "Merit distribution suggests balanced internal alignment. "
        )

        if "predicted_state" in agent_outputs.get("predictor", {}):
            summary += f"Prediction: {agent_outputs['predictor']['predicted_state']}. "

        if "recommendation" in agent_outputs.get("stabilizer", {}):
            summary += f"Stabilizer suggests: {agent_outputs['stabilizer']['recommendation']}."

        return NarrativeEvent(
            text=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_frame=frame,
        )
