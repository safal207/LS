from __future__ import annotations

import time
from typing import Callable

from .dampening import FieldDampening
from .evolution import FieldEvolution
from .resonance import FieldResonance
from .state import FieldNodeState, FieldState


class FieldRegistry:
    def __init__(
        self,
        ttl: float = 5.0,
        *,
        clock: Callable[[], float] | None = None,
        resonance: FieldResonance | None = None,
        dampening: FieldDampening | None = None,
        evolution: FieldEvolution | None = None,
    ) -> None:
        self.ttl = ttl
        self._clock = clock or time.time
        self._resonance = resonance
        self._dampening = dampening
        self._evolution = evolution
        self._nodes: dict[str, FieldNodeState] = {}

    def update_node(self, node_state: FieldNodeState) -> None:
        self._nodes[node_state.node_id] = node_state
        self._prune()

    def get_state(self) -> FieldState:
        self._prune()
        base_state = FieldState(nodes=dict(self._nodes))
        if self._resonance is None:
            return base_state
        metrics = self._resonance.compute(base_state)
        if self._dampening is not None:
            metrics = self._dampening.apply(metrics)
        if self._evolution is not None:
            weights = self._evolution.update(metrics)
            metrics = self._apply_weights(metrics, weights)
        return FieldState(nodes=base_state.nodes, metrics=metrics)

    @staticmethod
    def _apply_weights(metrics: dict[str, float], weights: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, value in metrics.items():
            if key == "orientation_coherence":
                weight = weights.get("coherence_weight", 1.0)
            elif key == "confidence_alignment":
                weight = weights.get("alignment_weight", 1.0)
            elif key == "trajectory_tension":
                weight = weights.get("tension_weight", 1.0)
            else:
                weight = 1.0
            scaled = float(value) * float(weight)
            if scaled < 0.0:
                scaled = 0.0
            if scaled > 1.0:
                scaled = 1.0
            out[key] = scaled
        return out

    def _prune(self) -> None:
        now = self._clock()
        expired = [node_id for node_id, state in self._nodes.items() if now - state.timestamp > self.ttl]
        for node_id in expired:
            self._nodes.pop(node_id, None)
