from __future__ import annotations

from ls.cognition.need_market_engine import Capability
from ls.memory.memory_graph import MemoryGraph


class CapabilityCalibrationEngine:
    def __init__(self, memory_graph: MemoryGraph, alpha: float = 0.2):
        self.memory_graph = memory_graph
        self.alpha = alpha

    def calibrate(self, capabilities: list[Capability]) -> list[Capability]:
        observed_effectiveness = self._compute_observed_effectiveness()

        calibrated: list[Capability] = []
        for capability in capabilities:
            observed = observed_effectiveness.get(capability.id)
            if observed is None:
                calibrated.append(capability)
                continue

            sample_count = len(observed["effects"])
            ema_value = observed["ema"]
            self.memory_graph.add_node(
                node_type="capability_observation",
                content={
                    "capability_id": capability.id,
                    "observed_effectiveness": ema_value,
                    "sample_count": sample_count,
                },
            )
            calibrated.append(
                Capability(
                    id=capability.id,
                    description=capability.description,
                    effectiveness=ema_value,
                    cost=capability.cost,
                )
            )

        return calibrated

    def _compute_observed_effectiveness(self) -> dict[str, dict[str, float | list[float]]]:
        effects_by_capability: dict[str, list[float]] = {}

        for action_node in self.memory_graph.find_nodes(node_type="action"):
            step = action_node.content.get("step")
            if not isinstance(step, str) or not step.startswith("apply_capability:"):
                continue

            capability_id = step.split(":", 1)[1]
            effects = effects_by_capability.setdefault(capability_id, [])

            for outcome_node in self.memory_graph.get_neighbors(action_node.node_id, relation="leads_to"):
                effect = outcome_node.content.get("effect")
                if isinstance(effect, (int, float)):
                    effects.append(float(effect))

        observed: dict[str, dict[str, float | list[float]]] = {}
        for capability_id, effects in effects_by_capability.items():
            if not effects:
                continue

            ema = effects[0]
            for effect in effects[1:]:
                ema = self.alpha * effect + (1.0 - self.alpha) * ema

            observed[capability_id] = {"ema": ema, "effects": effects}

        return observed
