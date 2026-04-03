# -*- coding: utf-8 -*-
"""
SystemObserver - meta-cognitive adequacy observer.

Monitors the full cognitive field (TemporalGraph + five forces) and
applies corrective Force 6 when pathologies are detected.

Pathologies:
  OVERHEATING        - all nodes are overheated; no discrimination remains
  OSSIFICATION       - the axis is frozen; the system ignores new signals
  VACUUM             - no active node exists; the field is empty
  SPLIT_BRAIN        - two modes are deadlocked; the system cannot choose
  RUNAWAY_CHAOS      - chaos compounds and the field destabilizes
  RESONANCE_COLLAPSE - the axis is too weak to guide decisions
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .temporal_graph import TemporalGraph

# -- Pathologies --------------------------------------------------------

OVERHEATING        = "OVERHEATING"         # mean resonance > _OVERHEAT_MEAN
OSSIFICATION       = "OSSIFICATION"        # axis unchanged > _OSSIFY_CYCLES
VACUUM             = "VACUUM"              # max resonance < _VACUUM_THRESH
SPLIT_BRAIN        = "SPLIT_BRAIN"         # two top nodes nearly tied at high resonance
RUNAWAY_CHAOS      = "RUNAWAY_CHAOS"       # chaos_trend < _CHAOS_COLLAPSE
RESONANCE_COLLAPSE = "RESONANCE_COLLAPSE"  # axis resonance < _WEAK_AXIS

# -- Thresholds ---------------------------------------------------------

_OVERHEAT_MEAN   = 0.82   # mean resonance => overheating
_VACUUM_THRESH   = 0.45   # max resonance => vacuum
_SPLIT_GAP       = 0.05   # top-2 gap when both > 0.70 => split-brain
_OSSIFY_CYCLES   = 8      # unchanged-axis cycles => ossification
_OSSIFY_BIAS     = 0.80   # axis stability_bias during ossification
_CHAOS_COLLAPSE  = -0.30  # chaos trend => runaway chaos
_WEAK_AXIS       = 0.35   # axis resonance => collapse
_SELF_LEARN_WINDOW_S = 60 * 60
_SELF_LEARN_REPEAT_THRESHOLD = 3

_SELF_LEARN_LESSON_MAP: Dict[str, str] = {
    OSSIFICATION: "lesson:meta:ossification_tendency",
    VACUUM: "lesson:meta:vacuum_tendency",
    OVERHEATING: "lesson:meta:overheating_tendency",
    SPLIT_BRAIN: "lesson:meta:split_brain_tendency",
    RUNAWAY_CHAOS: "lesson:meta:runaway_chaos_tendency",
    RESONANCE_COLLAPSE: "lesson:meta:resonance_collapse_tendency",
}

# Adequacy penalty applied per pathology
_PATHOLOGY_DEDUCTIONS: Dict[str, float] = {
    OVERHEATING:        0.15,
    OSSIFICATION:       0.20,
    VACUUM:             0.30,
    SPLIT_BRAIN:        0.25,
    RUNAWAY_CHAOS:      0.20,
    RESONANCE_COLLAPSE: 0.25,
}


# -- Report -------------------------------------------------------------

@dataclass
class AdequacyReport:
    """Result of one observation cycle."""
    score: float                    # 0.0 (crisis) -> 1.0 (healthy state)
    pathologies: List[str]          # detected pathology codes
    corrections: List[str]          # descriptions of applied corrections
    axis_id: Optional[str]          # current axis id
    timestamp: float = field(default_factory=time.time)

    @property
    def adequate(self) -> bool:
        """The system is operating normally."""
        return self.score >= 0.65

    @property
    def critical(self) -> bool:
        """The system is in a critical state."""
        return self.score < 0.40


# -- Observer -----------------------------------------------------------

class SystemObserver:
    """
    Meta-cognitive observer (Force 6).

    Runs after all five forces in each Coordinator.decide() cycle.
    Detects pathological states and applies corrective interventions
    directly to TemporalGraph nodes.

    Principle: the observer stays out of the way unless the field deviates.
    Its corrections are minimal and aim to restore dynamic
    equilibrium rather than imposing a specific state.
    """

    def __init__(self) -> None:
        # Report history (last 50 cycles)
        self._reports: deque[AdequacyReport] = deque(maxlen=50)
        # Counter for consecutive cycles with the same axis
        self._axis_tenure: Dict[str, int] = {}
        self._last_axis: Optional[str] = None
        # Feature 2: cumulative per-session pathology counter
        self._pathology_counts: Dict[str, int] = {}
        # After N repeats of one pathology, write a lesson:meta:* node
        _META_LESSON_THRESHOLD: int = 3
        self._meta_lesson_threshold = _META_LESSON_THRESHOLD
        self._last_self_lessons: set[str] = set()

    def _pathology_count_in_window(self, pathology: str, now_ts: float) -> int:
        cutoff = now_ts - _SELF_LEARN_WINDOW_S
        count = 0
        for report in self._reports:
            if report.timestamp < cutoff:
                continue
            if pathology in report.pathologies:
                count += 1
        return count

    def _inject_self_lessons(self, graph: "TemporalGraph", pathologies: List[str], now_ts: float) -> List[str]:
        injected: List[str] = []
        self._last_self_lessons = set()
        for pathology in pathologies:
            lesson_id = _SELF_LEARN_LESSON_MAP.get(pathology)
            if lesson_id is None:
                continue
            history_hits = self._pathology_count_in_window(pathology, now_ts)
            if (history_hits + 1) < _SELF_LEARN_REPEAT_THRESHOLD:
                continue
            graph.add_or_update(lesson_id, resonance=0.62, harmony_bonus=0.30, resting_resonance=0.45)
            self._last_self_lessons.add(lesson_id)
            injected.append(lesson_id)
        return injected

    # -- Main method ----------------------------------------------------

    def observe_and_correct(
        self,
        graph: "TemporalGraph",
        chaos_trend: float = 0.0,
    ) -> AdequacyReport:
        """
        1. Observe the current graph state and detect pathologies.
        2. Apply minimal corrective forces to nodes.
        3. Compute the adequacy score.
        4. Save the report to history.
        """
        pathologies: List[str] = []
        corrections: List[str] = []
        now_ts = time.time()

        nodes = list(graph.nodes.values())
        if not nodes:
            report = AdequacyReport(
                score=0.5,
                pathologies=[VACUUM],
                corrections=[],
                axis_id=None,
            )
            self._reports.append(report)
            return report

        axis_node = graph.get_meritocratic_axis()
        axis_id   = axis_node.id if axis_node else None

        # Update the continuous axis-tenure counter
        if axis_id is not None:
            if axis_id == self._last_axis:
                self._axis_tenure[axis_id] = self._axis_tenure.get(axis_id, 0) + 1
            else:
                self._axis_tenure = {axis_id: 1}
                self._last_axis = axis_id
        else:
            self._axis_tenure = {}
            self._last_axis = None

        # -- Pathology detection ---------------------------------------------

        resonances  = [n.resonance for n in nodes]
        mean_r      = sum(resonances) / len(resonances)
        max_r       = max(resonances)

        # 1. OVERHEATING: mean resonance above threshold -> field overheated
        if mean_r > _OVERHEAT_MEAN:
            pathologies.append(OVERHEATING)

        # 2. VACUUM: even the best node is below threshold -> vacuum
        if max_r < _VACUUM_THRESH:
            pathologies.append(VACUUM)

        # 3. OSSIFICATION: the same axis persisted too long and froze
        if (
            axis_id is not None
            and self._axis_tenure.get(axis_id, 0) >= _OSSIFY_CYCLES
            and axis_node is not None
            and axis_node.stability_bias >= _OSSIFY_BIAS
        ):
            pathologies.append(OSSIFICATION)

        # 4. SPLIT_BRAIN: top two nodes are both high and nearly tied
        sorted_nodes = sorted(nodes, key=lambda n: n.resonance, reverse=True)
        if (
            len(sorted_nodes) >= 2
            and sorted_nodes[0].resonance > 0.70
            and sorted_nodes[1].resonance > 0.70
            and (sorted_nodes[0].resonance - sorted_nodes[1].resonance) < _SPLIT_GAP
        ):
            pathologies.append(SPLIT_BRAIN)

        # 5. RUNAWAY_CHAOS: chaos trend is collapsing sharply
        if chaos_trend < _CHAOS_COLLAPSE:
            pathologies.append(RUNAWAY_CHAOS)

        # 6. RESONANCE_COLLAPSE: axis resonance is too weak
        if axis_node is not None and axis_node.resonance < _WEAK_AXIS:
            pathologies.append(RESONANCE_COLLAPSE)

        # -- Corrections (Force 6) -------------------------------------------

        if OVERHEATING in pathologies:
            # Normalize the full field: lower both resting and current resonance.
            # Resting resonance cannot be the floor here because it is overheated too.
            for n in nodes:
                n.resting_resonance = max(0.30, n.resting_resonance * 0.88)
                n.resonance = max(n.resting_resonance, n.resonance * 0.88)
            corrections.append("normalized field x0.88 (overheating)")

        if VACUUM in pathologies:
            # Raise both resting and current resonance of all nodes
            for n in nodes:
                rr = n.resting_resonance if n.resting_resonance is not None else 0.5
                n.resting_resonance = min(0.65, rr + 0.10)
                n.resonance = max(n.resonance, n.resting_resonance)
            # If no subconscious node exists, inject an anchor
            has_sub = any(n.id.startswith("subconscious:") for n in nodes)
            if not has_sub:
                graph.add_or_update("subconscious:deliberative", 0.55, 0.25)
                corrections.append("injected anchor node subconscious:deliberative (vacuum)")
            corrections.append("lifted resting resonances +0.10 (vacuum)")

        if OSSIFICATION in pathologies and axis_node is not None:
            # Lower stability_bias and nudge the axis down, including resting resonance.
            # The axis is frozen; unfreeze it fully, not only at current resonance.
            axis_node.stability_bias = max(0.0, axis_node.stability_bias - 0.30)
            axis_node.resting_resonance = max(0.30, axis_node.resting_resonance - 0.08)
            axis_node.resonance = max(axis_node.resting_resonance, axis_node.resonance - 0.08)
            # Reset tenure so other nodes get a chance
            self._axis_tenure[axis_id] = 0
            corrections.append(
                f"de-ossified '{axis_id}': stability_bias -{0.30:.2f}, nudge -0.08"
            )

        if SPLIT_BRAIN in pathologies and len(sorted_nodes) >= 2:
            weaker = sorted_nodes[1]
            # Use a fixed lower floor; resting is also elevated during split-brain.
            weaker.resonance = max(0.30, weaker.resonance - 0.12)
            corrections.append(
                f"resolved split-brain: suppressed '{weaker.id}' by 0.12"
            )

        if RUNAWAY_CHAOS in pathologies and axis_node is not None:
            # Boost the anchor axis as a counterweight to chaos
            axis_node.resonance = min(1.0, axis_node.resonance + 0.08)
            if axis_node.resting_resonance is not None:
                axis_node.resting_resonance = min(0.80, axis_node.resting_resonance + 0.05)
            corrections.append(f"chaos anchor: boosted '{axis_id}' +0.08 (runaway_chaos)")

        if RESONANCE_COLLAPSE in pathologies and axis_node is not None:
            # Emergency axis boost
            axis_node.resonance = min(1.0, axis_node.resonance + 0.15)
            corrections.append(f"emergency boost +0.15 for '{axis_id}' (resonance_collapse)")

        # -- Score ----------------------------------------------------------

        score = 1.0
        for p in pathologies:
            score -= _PATHOLOGY_DEDUCTIONS.get(p, 0.10)
        score = max(0.0, min(1.0, score))

        report = AdequacyReport(
            score=score,
            pathologies=pathologies,
            corrections=corrections,
            axis_id=axis_id,
            timestamp=now_ts,
        )
        self_lessons = self._inject_self_lessons(graph, pathologies, now_ts=now_ts)
        for lesson_id in self_lessons:
            corrections.append(f"self-learned '{lesson_id}' from repeated pathology")
        self._reports.append(report)

        # Feature 2: write meta-lessons for repeated pathologies
        self._maybe_write_meta_lessons(graph, pathologies)

        return report

    # -- Feature 2: observer meta-lessons --------------------------------

    def _maybe_write_meta_lessons(
        self, graph: "TemporalGraph", pathologies: List[str]
    ) -> None:
        """
        If the same pathology occurs >= _meta_lesson_threshold times,
        the observer writes a lesson:meta:* node into TemporalGraph.
        This lets the system remember its own weakness patterns.
        """
        for p in pathologies:
            self._pathology_counts[p] = self._pathology_counts.get(p, 0) + 1
            count = self._pathology_counts[p]
            if count == self._meta_lesson_threshold:
                node_id = f"lesson:meta:{p.lower()}_pattern"
                # resonance scales with pathology severity
                severity = _PATHOLOGY_DEDUCTIONS.get(p, 0.10)
                resonance = round(min(0.80, 0.45 + severity * 1.5), 3)
                graph.add_or_update(node_id, resonance, harmony_bonus=0.20)

    # -- Feature 6: session report ---------------------------------------

    def session_report(self, graph: "TemporalGraph") -> dict:
        """
        Final session analysis. Called during sleep consolidation.
        - Classifies session quality (easy / moderate / heavy)
        - Injects lesson:session:* nodes for dominant pathologies
        - Returns a dict for logging/observability
        """
        if not self._reports:
            return {"session_quality": "нет данных", "total_cycles": 0}

        from collections import Counter
        scores = [r.score for r in self._reports]
        avg_score = sum(scores) / len(scores)
        all_pathologies = [p for r in self._reports for p in r.pathologies]
        path_counts = Counter(all_pathologies)

        session_quality = (
            "лёгкая"    if avg_score > 0.80 else
            "умеренная" if avg_score > 0.60 else
            "тяжёлая"
        )

        injected: List[str] = []
        for pathology, count in path_counts.most_common(3):
            if count >= 2:
                node_id = f"lesson:session:{pathology.lower()}"
                resonance = round(min(0.75, 0.45 + count * 0.05), 3)
                graph.add_or_update(node_id, resonance, harmony_bonus=0.15)
                injected.append(node_id)

        return {
            "session_quality":        session_quality,
            "avg_adequacy":           round(avg_score, 3),
            "total_cycles":           len(self._reports),
            "pathology_counts":       dict(path_counts),
            "lesson_nodes_injected":  injected,
        }

    # -- Analytics --------------------------------------------------------

    def adequacy_trend(self) -> float:
        """
        Adequacy trend over the last N reports.
        Positive means improvement; negative means degradation.
        """
        if len(self._reports) < 4:
            return 0.0
        recent = list(self._reports)[-8:]
        half   = len(recent) // 2
        old_mean = sum(r.score for r in recent[:half]) / half
        new_mean = sum(r.score for r in recent[half:]) / (len(recent) - half)
        return round(new_mean - old_mean, 3)

    def last_report(self) -> Optional[AdequacyReport]:
        return self._reports[-1] if self._reports else None

    def stats(self) -> dict:
        if not self._reports:
            return {
                "score": 1.0,
                "adequate": True,
                "critical": False,
                "pathologies": [],
                "corrections": [],
                "self_lessons": [],
                "axis_tenure": 0,
                "trend": 0.0,
                "total_reports": 0,
            }
        last = self._reports[-1]
        return {
            "score":         round(last.score, 3),
            "adequate":      last.adequate,
            "critical":      last.critical,
            "pathologies":   last.pathologies,
            "corrections":   last.corrections,
            "self_lessons":  sorted(self._last_self_lessons),
            "axis_id":       last.axis_id,
            "axis_tenure":   self._axis_tenure.get(self._last_axis or "", 0),
            "trend":         self.adequacy_trend(),
            "total_reports": len(self._reports),
        }
