# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass, field
import threading
from typing import Dict, List, Tuple


@dataclass
class TemporalNode:
    id: str
    resonance: float = 1.0
    harmony_bonus: float = 0.5
    # Temporal velocity tracking
    last_updated: float = field(default_factory=time.time)
    velocity: float = 0.0          # resonance / second (positive = growing)
    _velocity_alpha: float = 0.4   # EMA smoothing factor (not serialised)

    def update_resonance(self, new_value: float) -> None:
        """Update resonance and recalculate velocity via EMA."""
        now = time.time()
        delta_r = new_value - self.resonance
        delta_t = max(now - self.last_updated, 0.1)   # floor at 100ms
        instant_velocity = delta_r / delta_t
        # Exponential moving average to smooth noisy spikes
        self.velocity = self._velocity_alpha * instant_velocity + (1 - self._velocity_alpha) * self.velocity
        self.resonance = max(0.0, min(1.0, new_value))
        self.last_updated = now

    def velocity_score(self, horizon_s: float = 60.0) -> float:
        """Projected resonance gain/loss over horizon_s seconds.

        Clamped to [-0.30, +0.40] so velocity can meaningfully shift axis
        selection without dominating pure resonance.
        """
        raw = self.velocity * horizon_s
        return max(-0.30, min(0.40, raw))


class TemporalGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, TemporalNode] = {}
        self._graph_lock = threading.Lock()

    def strengthen_strong_links(self, threshold: float = 0.75, boost: float = 0.15) -> int:
        """Увеличивает resonance узлов выше threshold на boost."""
        count = 0
        with self._graph_lock:
            for node in self.nodes.values():
                if node.resonance > threshold:
                    node.update_resonance(node.resonance + boost)
                    count += 1
        return count

    def prune_weak_nodes(self, threshold: float = 0.25, active_window: int = 100) -> int:
        """Удаляет узлы с resonance ниже threshold."""
        with self._graph_lock:
            snapshot = list(self.nodes.items())
        to_remove = [nid for nid, n in snapshot if n.resonance < threshold]
        with self._graph_lock:
            for nid in to_remove:
                self.nodes.pop(nid, None)
        return len(to_remove)

    def get_meritocratic_axis(self) -> TemporalNode | None:
        """Return the dominant node by resonance × (1 + harmony) + velocity_score.

        Velocity shifts the axis toward fast-growing patterns even before their
        absolute resonance catches up — predictive, not just reactive.
        """
        with self._graph_lock:
            nodes = list(self.nodes.values())
        if not nodes:
            return None
        return max(
            nodes,
            key=lambda n: n.resonance * (1 + n.harmony_bonus) + n.velocity_score(),
        )

    def velocity_leaders(self, n: int = 3) -> List[Tuple[str, float]]:
        """Return top-n nodes sorted by velocity (fastest growing first)."""
        with self._graph_lock:
            snapshot = [(node.id, node.velocity) for node in self.nodes.values()]
        return sorted(snapshot, key=lambda x: x[1], reverse=True)[:n]

    def apply_orientation_forces(
        self,
        chaos_score: float,
        harmony_score: float,
        drift_pressure: float,
        rhythm_phase: str = "neutral",
    ) -> dict[str, float]:
        """Apply OrientationCenter signals as forces on all nodes.

        Force rules (the "force ladder"):
          - chaos_score high  → weaken ALL nodes (disorder erodes patterns)
          - harmony_score high → strengthen the current axis node (coherence crystallises)
          - drift_pressure high → boost lesson:* nodes (drift calls for grounding in lessons)
          - rhythm_phase "inhale" → mild boost to reactive nodes
          - rhythm_phase "exhale" → mild boost to deliberative/creative nodes

        Returns dict of {node_id: delta_applied}.
        """
        deltas: dict[str, float] = {}
        chaos = max(0.0, min(1.0, chaos_score))
        harmony = max(0.0, min(1.0, harmony_score))
        drift = max(0.0, min(1.0, drift_pressure))

        # Determine current axis before modifying
        axis = self.get_meritocratic_axis()
        axis_id = axis.id if axis else None

        with self._graph_lock:
            for nid, node in list(self.nodes.items()):
                delta = 0.0

                # Chaos weakens everything (scaled: chaos 0.8 → -0.04 per node)
                if chaos > 0.3:
                    delta -= (chaos - 0.3) * 0.10

                # Harmony strengthens the axis
                if nid == axis_id and harmony > 0.5:
                    delta += (harmony - 0.5) * 0.16

                # Drift pressure boosts lesson nodes (grounding in experience)
                if nid.startswith("lesson:") and drift > 0.4:
                    delta += (drift - 0.4) * 0.12

                # Rhythm phase boosts matching mode
                if rhythm_phase == "inhale" and "reactive" in nid:
                    delta += 0.03
                elif rhythm_phase == "exhale" and any(m in nid for m in ("deliberative", "creative")):
                    delta += 0.03

                if delta != 0.0:
                    node.update_resonance(node.resonance + delta)
                    deltas[nid] = delta

        return deltas

    def to_orientation_signal(self) -> dict[str, float]:
        """Extract a trajectory/state signal from the temporal graph for OrientationCenter.

        Returns:
            trajectory_signal: axis resonance (0–1)      → quality of dominant pattern
            temporal_harmony:  mean resonance of nodes   → overall temporal coherence
            temporal_chaos:    std-dev of resonance      → how fragmented the graph is
            lesson_pressure:   sum of lesson resonances  → accumulated wisdom weight
        """
        with self._graph_lock:
            nodes = list(self.nodes.values())
        if not nodes:
            return {"trajectory_signal": 0.5, "temporal_harmony": 0.5,
                    "temporal_chaos": 0.0, "lesson_pressure": 0.0}

        resonances = [n.resonance for n in nodes]
        mean_r = sum(resonances) / len(resonances)
        variance = sum((r - mean_r) ** 2 for r in resonances) / len(resonances)
        std_r = variance ** 0.5

        axis = self.get_meritocratic_axis()
        axis_resonance = axis.resonance if axis else mean_r

        lesson_pressure = sum(
            n.resonance for n in nodes if n.id.startswith("lesson:")
        )

        return {
            "trajectory_signal": round(axis_resonance, 4),
            "temporal_harmony": round(mean_r, 4),
            "temporal_chaos": round(std_r, 4),
            "lesson_pressure": round(min(1.0, lesson_pressure / max(1, len(nodes))), 4),
        }

    def ingest_reflection(self, reason: str, progress: float) -> TemporalNode:
        """Convert a reflection result into a TemporalNode and add it to the graph.

        Nodes created here represent consolidated wisdom — lessons the system
        learned about itself. They have high harmony_bonus so they survive
        competition with transient subconscious nodes.

        resonance = clamp(0.1, 0.95, 0.5 + progress * 0.45)
        harmony_bonus = 0.35 (lessons are structurally valuable)
        """
        resonance = max(0.10, min(0.95, 0.5 + progress * 0.45))
        # Stable id: first 12 chars of reason as slug, avoids duplicates on repeated ingestion
        slug = "".join(c if c.isalnum() else "_" for c in reason[:20]).strip("_").lower()
        node_id = f"lesson:{slug}"
        with self._graph_lock:
            existing = self.nodes.get(node_id)
            if existing is not None:
                # Lesson confirmed again — strengthen it
                existing.update_resonance(max(existing.resonance, resonance))
                return existing
            node = TemporalNode(id=node_id, resonance=resonance, harmony_bonus=0.35)
            self.nodes[node_id] = node
        self.align_to_axis(node)
        return node

    def align_to_axis(self, new_node: TemporalNode) -> float:
        """Align new node to axis. Returns synergy (0–1)."""
        axis = self.get_meritocratic_axis()
        if not axis:
            return 0.0
        synergy = min(1.0, new_node.resonance * 0.7 + (1 - abs(new_node.resonance - axis.resonance)) * 0.3)
        new_node.update_resonance(new_node.resonance + synergy * 0.1)
        return synergy
