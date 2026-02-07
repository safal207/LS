from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from .base import NarrativeEvent
from ..visualization import render_attention, render_bar


@dataclass
class NarrativeGenerator:
    def generate(self, frame: Dict[str, Any], agent_outputs: Dict[str, Any]) -> NarrativeEvent:
        state = frame.get("system_state")
        decision = frame.get("decision", {})
        choice = decision.get("choice", "unknown")
        reasons = decision.get("reasons", [])
        hardware = frame.get("hardware", {}) if isinstance(frame.get("hardware", {}), dict) else {}
        lri = hardware.get("lri", {}) if isinstance(hardware.get("lri", {}), dict) else {}
        strain = lri.get("state")
        strain_value = lri.get("value")

        summary = (
            f"System is in state '{state}'. "
            f"Selected model '{choice}' due to {', '.join(reasons)}. "
            "Merit distribution suggests balanced internal alignment. "
        )
        if isinstance(strain, str):
            summary += f"System strain reported as '{strain}'. "
        if isinstance(strain_value, (int, float)):
            summary += f"Load index {render_bar(float(strain_value), width=12)}. "
        attention = frame.get("attention_distribution", {})
        if isinstance(attention, dict) and attention:
            summary += f"Attention {render_attention(attention)}. "

        if "predicted_state" in agent_outputs.get("predictor", {}):
            summary += f"Prediction: {agent_outputs['predictor']['predicted_state']}. "

        if "recommendation" in agent_outputs.get("stabilizer", {}):
            summary += f"Stabilizer suggests: {agent_outputs['stabilizer']['recommendation']}."

        return NarrativeEvent(
            text=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_frame=frame,
        )
