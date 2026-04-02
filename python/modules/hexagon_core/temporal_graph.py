# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass, field
import threading
from typing import Dict, List, Optional, Tuple


# ─── Half-life constants for forgetting curve (seconds) ───────────────────────
_HALF_LIFE: dict[str, float] = {
    "subconscious:":   600.0,  # 10 min — transient cognitive mode hints
    "world:git:":     3600.0,  # 1 h    — git commits matter briefly
    "world:error:":   1800.0,  # 30 min — errors are urgent but fade
    "world:critical:": 300.0,  # 5 min  — critical: urgent, must act NOW, then clear
    "world:custom:":  1800.0,  # 30 min
    "lesson:":       86400.0,  # 24 h   — lessons persist
}
_DEFAULT_HALF_LIFE = 3600.0


def _half_life_for(node_id: str) -> float:
    for prefix, hl in _HALF_LIFE.items():
        if node_id.startswith(prefix):
            return hl
    return _DEFAULT_HALF_LIFE


# ─── Interference pairs (competing modes weaken each other) ───────────────────
_INTERFERENCE_PAIRS: list[tuple[str, str]] = [
    ("subconscious:reactive", "subconscious:deliberative"),
    ("subconscious:reactive", "subconscious:creative"),
]
_INTERFERENCE_STRENGTH = 0.04   # max mutual weakening per pair


@dataclass
class TemporalNode:
    id: str
    resonance: float = 1.0
    harmony_bonus: float = 0.5

    # Velocity tracking
    last_updated: float = field(default_factory=time.time)
    velocity: float = 0.0
    _velocity_alpha: float = 0.4

    # Stabilization tracking
    resting_resonance: float = field(default=None)   # type: ignore[assignment]
    stability_bias: float = 0.0   # 0–1: resistance to displacement; grows when stable

    def __post_init__(self) -> None:
        if self.resting_resonance is None:          # type: ignore[comparison-overlap]
            self.resting_resonance = self.resonance

    def update_resonance(self, new_value: float) -> None:
        """Update resonance, recalculate velocity (EMA), and update stability_bias."""
        now = time.time()
        delta_r = new_value - self.resonance
        delta_t = max(now - self.last_updated, 0.1)
        instant_velocity = delta_r / delta_t
        self.velocity = self._velocity_alpha * instant_velocity + \
                        (1 - self._velocity_alpha) * self.velocity
        self.resonance = max(0.0, min(1.0, new_value))
        self.last_updated = now

        # Stability_bias: grows when nearly stationary, decays when changing fast
        vel_mag = abs(self.velocity)
        if vel_mag < 0.005:                                  # nearly stationary
            self.stability_bias = min(1.0, self.stability_bias + 0.015)
        else:
            self.stability_bias = max(0.0, self.stability_bias - vel_mag * 0.4)

        # Resting resonance: slow EMA — tracks the "home" level
        self.resting_resonance = 0.97 * self.resting_resonance + 0.03 * self.resonance

    def velocity_score(self, horizon_s: float = 60.0) -> float:
        """Projected gain/loss clamped to [-0.30, +0.40]."""
        return max(-0.30, min(0.40, self.velocity * horizon_s))

    def stability_score(self) -> float:
        """Contribution of stability to axis selection (max +0.18)."""
        return self.stability_bias * 0.18


# ─── Orientation snapshot for trajectory tracking ─────────────────────────────

@dataclass
class OrientationSnapshot:
    ts: float
    trajectory_signal: float
    chaos_score: float
    harmony_score: float
    drift_pressure: float
    rhythm_phase: str
    axis_id: str
    axis_resonance: float


class TemporalGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, TemporalNode] = {}
        self._graph_lock = threading.Lock()

        # Orientation trajectory history (last 60 snapshots)
        self._orientation_history: List[OrientationSnapshot] = []
        self._orientation_lock = threading.Lock()

    # ── Core graph ops ────────────────────────────────────────────────────────

    def strengthen_strong_links(self, threshold: float = 0.75, boost: float = 0.15) -> int:
        count = 0
        with self._graph_lock:
            for node in self.nodes.values():
                if node.resonance > threshold:
                    node.update_resonance(node.resonance + boost)
                    count += 1
        return count

    def prune_weak_nodes(self, threshold: float = 0.25, active_window: int = 100) -> int:
        with self._graph_lock:
            snapshot = list(self.nodes.items())
        to_remove = [nid for nid, n in snapshot if n.resonance < threshold]
        with self._graph_lock:
            for nid in to_remove:
                self.nodes.pop(nid, None)
        return len(to_remove)

    def get_meritocratic_axis(self) -> Optional[TemporalNode]:
        """Dominant node by resonance × (1+harmony) + velocity_score + stability_score.

        Three forces compete:
          resonance×harmony — absolute strength
          velocity_score    — growth momentum (predictive)
          stability_score   — inertia (resistant to displacement)
        """
        with self._graph_lock:
            nodes = list(self.nodes.values())
        if not nodes:
            return None
        return max(
            nodes,
            key=lambda n: (
                n.resonance * (1 + n.harmony_bonus)
                + n.velocity_score()
                + n.stability_score()
            ),
        )

    def velocity_leaders(self, n: int = 3) -> List[Tuple[str, float]]:
        with self._graph_lock:
            snapshot = [(node.id, node.velocity) for node in self.nodes.values()]
        return sorted(snapshot, key=lambda x: x[1], reverse=True)[:n]

    # ── Force 1 & 2: Orientation forces (existing) ────────────────────────────

    def apply_orientation_forces(
        self,
        chaos_score: float,
        harmony_score: float,
        drift_pressure: float,
        rhythm_phase: str = "neutral",
    ) -> dict[str, float]:
        """Downward forces from OrientationCenter into graph nodes."""
        deltas: dict[str, float] = {}
        chaos   = max(0.0, min(1.0, chaos_score))
        harmony = max(0.0, min(1.0, harmony_score))
        drift   = max(0.0, min(1.0, drift_pressure))

        axis    = self.get_meritocratic_axis()
        axis_id = axis.id if axis else None

        with self._graph_lock:
            for nid, node in list(self.nodes.items()):
                delta = 0.0

                # Chaos weakens all (high stability resists it)
                if chaos > 0.3:
                    raw_chaos = (chaos - 0.3) * 0.10
                    delta -= raw_chaos * (1.0 - node.stability_bias * 0.6)

                # Harmony strengthens axis
                if nid == axis_id and harmony > 0.5:
                    delta += (harmony - 0.5) * 0.16

                # Drift boosts lessons
                if nid.startswith("lesson:") and drift > 0.4:
                    delta += (drift - 0.4) * 0.12

                # Rhythm phase
                if rhythm_phase == "inhale" and "reactive" in nid:
                    delta += 0.03
                elif rhythm_phase == "exhale" and any(m in nid for m in ("deliberative", "creative")):
                    delta += 0.03

                if delta != 0.0:
                    node.update_resonance(node.resonance + delta)
                    deltas[nid] = delta

        return deltas

    # ── Force 3: Stabilization ─────────────────────────────────────────────────

    def apply_stabilization_forces(self, strength: float = 0.06) -> dict[str, float]:
        """Mean-reversion + hysteresis — the holding force.

        Each node is pulled toward its resting_resonance (where it "wants" to be).
        The axis node gets an extra stability bonus if it has been stable for a while.
        The pull is scaled by (1 - stability_bias) so highly stable nodes move less.

        This prevents the axis from thrashing during transient disturbances.
        """
        deltas: dict[str, float] = {}
        axis    = self.get_meritocratic_axis()
        axis_id = axis.id if axis else None

        with self._graph_lock:
            for nid, node in list(self.nodes.items()):
                # Mean-reversion: pull toward resting state
                pull = (node.resting_resonance - node.resonance) * strength
                # Scale by (1 - stability_bias): stable nodes resist being pulled
                pull *= max(0.1, 1.0 - node.stability_bias * 0.7)

                # Axis hysteresis: if stable axis, give it a small consolidation boost
                if nid == axis_id and node.stability_bias > 0.4:
                    pull += node.stability_bias * 0.012

                if abs(pull) > 1e-5:
                    node.update_resonance(node.resonance + pull)
                    deltas[nid] = round(pull, 6)

        return deltas

    # ── Force 4: Forgetting curve ──────────────────────────────────────────────

    def apply_decay(self, dt_s: float = 60.0) -> dict[str, float]:
        """Natural resonance decay toward resting_resonance over time.

        Each node decays with its own half-life based on type.
        Nodes reinforced recently (low |velocity| but high stability) decay slower.
        """
        deltas: dict[str, float] = {}
        with self._graph_lock:
            for nid, node in list(self.nodes.items()):
                hl = _half_life_for(nid)
                # Decay constant λ = ln(2) / half_life
                decay_rate = 0.693 / hl
                # How much to decay: exponential step for dt_s
                # Approximate: delta = -decay_rate * dt_s * (resonance - resting)
                gap = node.resonance - node.resting_resonance
                if abs(gap) < 1e-4:
                    continue
                delta = -decay_rate * dt_s * gap
                # Stability bias slows decay (stable nodes retain resonance longer)
                delta *= (1.0 - node.stability_bias * 0.5)
                node.update_resonance(node.resonance + delta)
                deltas[nid] = round(delta, 6)
        return deltas

    # ── Force 5: Cross-node interference ──────────────────────────────────────

    def apply_interference(self) -> dict[str, float]:
        """Competing mode nodes weaken each other (anti-split-brain).

        When two conflicting modes are both highly resonant, they partially cancel.
        Interference is proportional to the product of their resonances,
        so weak competitors don't cancel the dominant pattern.
        """
        deltas: dict[str, float] = {}
        with self._graph_lock:
            for a_id, b_id in _INTERFERENCE_PAIRS:
                node_a = self.nodes.get(a_id)
                node_b = self.nodes.get(b_id)
                if node_a is None or node_b is None:
                    continue
                # Interference strength scales with product of resonances
                interference = node_a.resonance * node_b.resonance * _INTERFERENCE_STRENGTH
                # The weaker node absorbs more interference
                if node_a.resonance < node_b.resonance:
                    node_a.update_resonance(node_a.resonance - interference)
                    deltas[a_id] = deltas.get(a_id, 0.0) - interference
                else:
                    node_b.update_resonance(node_b.resonance - interference)
                    deltas[b_id] = deltas.get(b_id, 0.0) - interference
        return deltas

    # ── Orientation trajectory ─────────────────────────────────────────────────

    def record_orientation_snapshot(self, orientation: dict) -> None:
        """Record a snapshot of OrientationCenter state for trajectory tracking."""
        axis = self.get_meritocratic_axis()
        snap = OrientationSnapshot(
            ts=time.time(),
            trajectory_signal=float(orientation.get("trajectory_signal", 0.5)),
            chaos_score=float(orientation.get("chaos_score", 0.0)),
            harmony_score=float(orientation.get("harmony_score", 0.0)),
            drift_pressure=float(orientation.get("drift_pressure", 0.0)),
            rhythm_phase=str(orientation.get("rhythm_phase", "neutral")),
            axis_id=axis.id if axis else "",
            axis_resonance=axis.resonance if axis else 0.0,
        )
        with self._orientation_lock:
            self._orientation_history.append(snap)
            if len(self._orientation_history) > 60:
                self._orientation_history = self._orientation_history[-60:]

    def get_orientation_momentum(self) -> dict[str, float]:
        """Compute the direction and speed of change in OrientationCenter state.

        Returns:
            chaos_trend:   positive = chaos rising, negative = chaos falling
            harmony_trend: positive = harmony rising
            axis_stability: how long the current axis has been dominant (0–1)
            momentum:      overall signed trend strength (-1 = deteriorating, +1 = improving)
        """
        with self._orientation_lock:
            history = list(self._orientation_history)

        if len(history) < 2:
            return {"chaos_trend": 0.0, "harmony_trend": 0.0,
                    "axis_stability": 0.0, "momentum": 0.0}

        recent = history[-5:]   # last 5 snapshots
        older  = history[-10:-5] if len(history) >= 10 else history[:max(1, len(history)//2)]

        def mean(seq, key):
            vals = [getattr(s, key) for s in seq]
            return sum(vals) / len(vals) if vals else 0.0

        chaos_trend   = mean(recent, "chaos_score")   - mean(older, "chaos_score")
        harmony_trend = mean(recent, "harmony_score") - mean(older, "harmony_score")

        # Axis stability: fraction of recent snapshots where axis_id is the same
        current_axis_id = history[-1].axis_id
        same_axis = sum(1 for s in recent if s.axis_id == current_axis_id)
        axis_stability = same_axis / len(recent) if recent else 0.0

        # Momentum: improving = harmony rising + chaos falling + axis stable
        # axis_stability acts as a small tie-breaker, not a dominant signal
        momentum = (
            -chaos_trend * 0.5
            + harmony_trend * 0.4
            + (axis_stability - 0.5) * 0.1
        )

        return {
            "chaos_trend":     round(chaos_trend, 4),
            "harmony_trend":   round(harmony_trend, 4),
            "axis_stability":  round(axis_stability, 4),
            "momentum":        round(max(-1.0, min(1.0, momentum)), 4),
        }

    # ── Outward signal ─────────────────────────────────────────────────────────

    def to_orientation_signal(self) -> dict[str, float]:
        """Extract temporal state signal for OrientationCenter input."""
        with self._graph_lock:
            nodes = list(self.nodes.values())
        if not nodes:
            return {"trajectory_signal": 0.5, "temporal_harmony": 0.5,
                    "temporal_chaos": 0.0, "lesson_pressure": 0.0,
                    "stability_index": 0.0, "momentum": 0.0}

        resonances = [n.resonance for n in nodes]
        mean_r = sum(resonances) / len(resonances)
        variance = sum((r - mean_r) ** 2 for r in resonances) / len(resonances)

        axis = self.get_meritocratic_axis()
        axis_resonance = axis.resonance if axis else mean_r
        stability_index = axis.stability_bias if axis else 0.0

        lesson_pressure = sum(n.resonance for n in nodes if n.id.startswith("lesson:"))
        momentum = self.get_orientation_momentum().get("momentum", 0.0)

        return {
            "trajectory_signal": round(axis_resonance, 4),
            "temporal_harmony":  round(mean_r, 4),
            "temporal_chaos":    round(variance ** 0.5, 4),
            "lesson_pressure":   round(min(1.0, lesson_pressure / max(1, len(nodes))), 4),
            "stability_index":   round(stability_index, 4),
            "momentum":          round(momentum, 4),
        }

    # ── Reflection ingestion ───────────────────────────────────────────────────

    def ingest_reflection(self, reason: str, progress: float) -> TemporalNode:
        """Convert reflection result into a persistent lesson TemporalNode."""
        resonance = max(0.10, min(0.95, 0.5 + progress * 0.45))
        slug = "".join(c if c.isalnum() else "_" for c in reason[:20]).strip("_").lower()
        node_id = f"lesson:{slug}"
        with self._graph_lock:
            existing = self.nodes.get(node_id)
            if existing is not None:
                existing.update_resonance(max(existing.resonance, resonance))
                return existing
            node = TemporalNode(id=node_id, resonance=resonance, harmony_bonus=0.35)
            self.nodes[node_id] = node
        self.align_to_axis(node)
        return node

    # ── Axis alignment ─────────────────────────────────────────────────────────

    def align_to_axis(self, new_node: TemporalNode) -> float:
        axis = self.get_meritocratic_axis()
        if not axis:
            return 0.0
        synergy = min(1.0, new_node.resonance * 0.7 +
                      (1 - abs(new_node.resonance - axis.resonance)) * 0.3)
        new_node.update_resonance(new_node.resonance + synergy * 0.1)
        return synergy
