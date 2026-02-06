from __future__ import annotations

import time
from typing import Callable

from .dampening import FieldDampening
from .evolution import FieldEvolution
from .mesh import CognitiveMesh
from .morphogenesis import FieldMorphogenesis
from .reflexivity import FieldReflexivity
from .resonance import FieldResonance
from .state import FieldNodeState, FieldState
from .topology import CognitiveTopology


class FieldRegistry:
    def __init__(
        self,
        ttl: float = 5.0,
        *,
        clock: Callable[[], float] | None = None,
        resonance: FieldResonance | None = None,
        dampening: FieldDampening | None = None,
        evolution: FieldEvolution | None = None,
        mesh: CognitiveMesh | None = None,
        morphogenesis: FieldMorphogenesis | None = None,
        topology: CognitiveTopology | None = None,
        reflexivity: FieldReflexivity | None = None,
    ) -> None:
        self.ttl = ttl
        self._clock = clock or time.time
        self._resonance = resonance
        self._dampening = dampening
        self._evolution = evolution
        self._mesh = mesh
        self._morphogenesis = morphogenesis
        self._topology = topology
        self._reflexivity = reflexivity
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
        if self._mesh is not None:
            mesh_state = self._mesh.update(metrics)
            metrics = self.applymesh(metrics, mesh_state)
            if self._morphogenesis is not None:
                morphology = self._morphogenesis.update(mesh_state, metrics)
                metrics = self.applymorphology(metrics, morphology)
            if self._topology is not None:
                self._topology.update(metrics, mesh_state)
                metrics = self.applytopology(metrics, self._topology)
        if self._reflexivity is not None:
            adjustments = self._reflexivity.update(metrics)
            metrics = self.applyreflexivity(metrics, adjustments)
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

    @staticmethod
    def applymesh(metrics: dict[str, float], mesh: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, value in metrics.items():
            base = (
                key.replace("orientation_", "")
                .replace("confidence_", "")
                .replace("trajectory_", "")
            )
            pattern = mesh.get(f"{base}_pattern", 0.0)
            blended = (float(value) + float(pattern)) / 2.0
            if blended < 0.0:
                blended = 0.0
            if blended > 1.0:
                blended = 1.0
            out[key] = blended
        return out

    @staticmethod
    def applymorphology(metrics: dict[str, float], morph: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, value in metrics.items():
            if key == "orientation_coherence":
                scale = morph.get("coherence_scale", 1.0)
            elif key == "confidence_alignment":
                scale = morph.get("alignment_scale", 1.0)
            elif key == "trajectory_tension":
                scale = morph.get("tension_scale", 1.0)
            else:
                scale = 1.0

            scaled = float(value) * float(scale)
            if scaled < 0.0:
                scaled = 0.0
            if scaled > 1.0:
                scaled = 1.0
            out[key] = scaled
        return out

    @staticmethod
    def applytopology(metrics: dict[str, float], topology: CognitiveTopology) -> dict[str, float]:
        return topology.apply(metrics)

    @staticmethod
    def applyreflexivity(
        metrics: dict[str, float],
        adj: dict[str, float],
    ) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, value in metrics.items():
            delta = adj.get(key, 0.0)
            new = float(value) + float(delta)
            if new < 0.0:
                new = 0.0
            if new > 1.0:
                new = 1.0
            out[key] = new
        return out

    def _prune(self) -> None:
        now = self._clock()
        expired = [node_id for node_id, state in self._nodes.items() if now - state.timestamp > self.ttl]
        for node_id in expired:
            self._nodes.pop(node_id, None)
