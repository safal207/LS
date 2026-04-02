# -*- coding: utf-8 -*-
"""Tests for OrientationCenter ↔ TemporalGraph force ladder."""
from __future__ import annotations

import os, sys, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODULES = os.path.join(ROOT, "python", "modules")
for p in (ROOT, MODULES):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexagon_core.temporal_graph import TemporalGraph, TemporalNode


class TestOrientationForces(unittest.TestCase):

    def _graph_with_nodes(self) -> TemporalGraph:
        tg = TemporalGraph()
        tg.nodes["subconscious:deliberative"] = TemporalNode(
            id="subconscious:deliberative", resonance=0.80, harmony_bonus=0.2
        )
        tg.nodes["subconscious:reactive"] = TemporalNode(
            id="subconscious:reactive", resonance=0.60, harmony_bonus=0.1
        )
        tg.nodes["lesson:approach_worked"] = TemporalNode(
            id="lesson:approach_worked", resonance=0.70, harmony_bonus=0.35
        )
        tg.nodes["world:git:abc123"] = TemporalNode(
            id="world:git:abc123", resonance=0.55, harmony_bonus=0.1
        )
        return tg

    def test_high_chaos_weakens_all_nodes(self):
        tg = self._graph_with_nodes()
        before = {nid: n.resonance for nid, n in tg.nodes.items()}

        tg.apply_orientation_forces(chaos_score=0.9, harmony_score=0.3,
                                    drift_pressure=0.2, rhythm_phase="neutral")

        for nid, node in tg.nodes.items():
            self.assertLessEqual(node.resonance, before[nid] + 1e-9,
                                 f"{nid} should not increase under high chaos")

    def test_high_harmony_strengthens_axis(self):
        tg = self._graph_with_nodes()
        axis_before = tg.get_meritocratic_axis()
        axis_r_before = axis_before.resonance

        tg.apply_orientation_forces(chaos_score=0.1, harmony_score=0.9,
                                    drift_pressure=0.1, rhythm_phase="neutral")

        axis_after = tg.nodes[axis_before.id]
        self.assertGreater(axis_after.resonance, axis_r_before,
                           "Axis node should strengthen under high harmony")

    def test_drift_pressure_boosts_lesson_nodes(self):
        tg = self._graph_with_nodes()
        lesson_r_before = tg.nodes["lesson:approach_worked"].resonance

        tg.apply_orientation_forces(chaos_score=0.2, harmony_score=0.3,
                                    drift_pressure=0.9, rhythm_phase="neutral")

        lesson_r_after = tg.nodes["lesson:approach_worked"].resonance
        self.assertGreater(lesson_r_after, lesson_r_before,
                           "Lesson nodes should strengthen under high drift pressure")

    def test_inhale_phase_boosts_reactive(self):
        tg = self._graph_with_nodes()
        reactive_r_before = tg.nodes["subconscious:reactive"].resonance

        tg.apply_orientation_forces(chaos_score=0.1, harmony_score=0.3,
                                    drift_pressure=0.1, rhythm_phase="inhale")

        reactive_r_after = tg.nodes["subconscious:reactive"].resonance
        self.assertGreater(reactive_r_after, reactive_r_before,
                           "Reactive node should boost on inhale phase")

    def test_exhale_phase_boosts_deliberative(self):
        tg = self._graph_with_nodes()
        delib_r_before = tg.nodes["subconscious:deliberative"].resonance

        tg.apply_orientation_forces(chaos_score=0.1, harmony_score=0.3,
                                    drift_pressure=0.1, rhythm_phase="exhale")

        delib_r_after = tg.nodes["subconscious:deliberative"].resonance
        self.assertGreater(delib_r_after, delib_r_before,
                           "Deliberative node should boost on exhale phase")

    def test_to_orientation_signal_reflects_graph_state(self):
        tg = self._graph_with_nodes()
        sig = tg.to_orientation_signal()

        self.assertIn("trajectory_signal", sig)
        self.assertIn("temporal_harmony", sig)
        self.assertIn("temporal_chaos", sig)
        self.assertIn("lesson_pressure", sig)

        # trajectory_signal should match axis resonance
        axis = tg.get_meritocratic_axis()
        self.assertAlmostEqual(sig["trajectory_signal"], axis.resonance, places=3)

    def test_to_orientation_signal_empty_graph(self):
        tg = TemporalGraph()
        sig = tg.to_orientation_signal()
        self.assertEqual(sig["trajectory_signal"], 0.5)

    def test_high_axis_resonance_reduces_trajectory_error(self):
        """When temporal axis resonance is high, blended trajectory_error should decrease."""
        tg = TemporalGraph()
        tg.nodes["subconscious:deliberative"] = TemporalNode(
            id="subconscious:deliberative", resonance=0.95, harmony_bonus=0.2
        )
        sig = tg.to_orientation_signal()
        base_error = 0.8
        t_signal = sig["trajectory_signal"]
        blended = base_error * 0.7 + (1.0 - t_signal) * 0.3
        self.assertLess(blended, base_error,
                        "High axis resonance should reduce trajectory error")

    def test_force_ladder_bidirectional(self):
        """Full cycle: orientation forces flow into graph, graph signal flows back."""
        tg = self._graph_with_nodes()

        # Step 1: read signal OUT of graph
        signal = tg.to_orientation_signal()
        self.assertGreater(signal["trajectory_signal"], 0.0)

        # Step 2: apply orientation forces INTO graph
        deltas = tg.apply_orientation_forces(
            chaos_score=0.2,
            harmony_score=0.8,
            drift_pressure=0.3,
            rhythm_phase="exhale",
        )
        # At least some nodes should have changed
        self.assertGreater(len(deltas), 0)

        # Step 3: signal OUT again — should reflect the changes
        signal_after = tg.to_orientation_signal()
        # With high harmony boosting axis, trajectory_signal should be >= before
        self.assertGreaterEqual(signal_after["trajectory_signal"],
                                signal["trajectory_signal"] - 0.01)  # small tolerance


if __name__ == "__main__":
    unittest.main()
