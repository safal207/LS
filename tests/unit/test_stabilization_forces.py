# -*- coding: utf-8 -*-
"""Tests for stabilization force, forgetting curve, interference, and trajectory."""
from __future__ import annotations

import os, sys, time, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODULES = os.path.join(ROOT, "python", "modules")
for p in (ROOT, MODULES):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexagon_core.temporal_graph import TemporalGraph, TemporalNode, _half_life_for


def _graph() -> TemporalGraph:
    tg = TemporalGraph()
    tg.nodes["subconscious:deliberative"] = TemporalNode(
        id="subconscious:deliberative", resonance=0.80, harmony_bonus=0.2)
    tg.nodes["subconscious:reactive"] = TemporalNode(
        id="subconscious:reactive", resonance=0.65, harmony_bonus=0.1)
    tg.nodes["lesson:works_well"] = TemporalNode(
        id="lesson:works_well", resonance=0.70, harmony_bonus=0.35)
    return tg


class TestStabilityBias(unittest.TestCase):
    def test_stability_grows_when_stationary(self):
        node = TemporalNode(id="test", resonance=0.70)
        # Simulate many tiny changes (velocity stays near zero)
        for _ in range(10):
            time.sleep(0.02)
            node.update_resonance(0.70)  # no delta → velocity ≈ 0
        self.assertGreater(node.stability_bias, 0.0)

    def test_stability_decays_when_changing_fast(self):
        node = TemporalNode(id="test", resonance=0.50, stability_bias=0.8)
        time.sleep(0.05)
        node.update_resonance(0.95)   # large fast jump
        self.assertLess(node.stability_bias, 0.8)

    def test_stable_node_wins_axis_over_equal_resonance(self):
        tg = TemporalGraph()
        stable = TemporalNode(id="a:stable", resonance=0.75,
                              harmony_bonus=0.1, stability_bias=0.9)
        fresh  = TemporalNode(id="b:fresh",  resonance=0.75,
                              harmony_bonus=0.1, stability_bias=0.0)
        tg.nodes["a:stable"] = stable
        tg.nodes["b:fresh"]  = fresh
        axis = tg.get_meritocratic_axis()
        self.assertEqual(axis.id, "a:stable",
                         "Stable node should win tie via stability_score")

    def test_stability_resists_chaos_weakening(self):
        tg = _graph()
        # Give deliberative high stability
        tg.nodes["subconscious:deliberative"].stability_bias = 0.95
        r_before = tg.nodes["subconscious:deliberative"].resonance

        tg.apply_orientation_forces(chaos_score=0.9, harmony_score=0.1,
                                    drift_pressure=0.1, rhythm_phase="neutral")
        r_after = tg.nodes["subconscious:deliberative"].resonance

        # Should lose less resonance than a node without stability
        tg2 = _graph()
        tg2.nodes["subconscious:deliberative"].stability_bias = 0.0
        tg2.apply_orientation_forces(chaos_score=0.9, harmony_score=0.1,
                                     drift_pressure=0.1, rhythm_phase="neutral")
        r_unstable = tg2.nodes["subconscious:deliberative"].resonance
        self.assertGreater(r_after, r_unstable,
                           "Stable node should lose less to chaos")


class TestStabilizationForce(unittest.TestCase):
    def test_above_resting_pulled_down(self):
        node = TemporalNode(id="x", resonance=0.90, resting_resonance=0.60)
        tg = TemporalGraph()
        tg.nodes["x"] = node
        tg.apply_stabilization_forces(strength=0.1)
        self.assertLess(tg.nodes["x"].resonance, 0.90,
                        "Node above resting should be pulled down")

    def test_below_resting_pulled_up(self):
        node = TemporalNode(id="x", resonance=0.30, resting_resonance=0.70)
        tg = TemporalGraph()
        tg.nodes["x"] = node
        tg.apply_stabilization_forces(strength=0.1)
        self.assertGreater(tg.nodes["x"].resonance, 0.30,
                           "Node below resting should be pulled up")

    def test_stable_axis_gets_consolidation_boost(self):
        tg = _graph()
        axis = tg.get_meritocratic_axis()
        axis.stability_bias = 0.8
        r_before = axis.resonance
        tg.apply_stabilization_forces(strength=0.06)
        self.assertGreaterEqual(tg.nodes[axis.id].resonance, r_before - 0.01,
                                "Stable axis should not lose resonance (may gain)")


class TestForgettingCurve(unittest.TestCase):
    def test_half_life_ordering(self):
        # Lessons (24h) > subconscious (10m) > world:critical (5m — urgent, clear fast)
        hl_lesson = _half_life_for("lesson:something")
        hl_sub    = _half_life_for("subconscious:reactive")
        hl_crit   = _half_life_for("world:critical:abc")
        hl_git    = _half_life_for("world:git:abc")
        self.assertGreater(hl_lesson, hl_sub)
        self.assertGreater(hl_sub, hl_crit)       # subconscious outlasts critical
        self.assertGreater(hl_git, hl_crit)        # git history outlasts critical alerts

    def test_decay_reduces_resonance_above_resting(self):
        tg = TemporalGraph()
        node = TemporalNode(id="subconscious:reactive",
                            resonance=0.90, resting_resonance=0.50)
        tg.nodes["subconscious:reactive"] = node
        tg.apply_decay(dt_s=600.0)   # 10 minutes
        self.assertLess(tg.nodes["subconscious:reactive"].resonance, 0.90)

    def test_lesson_decays_slower_than_subconscious(self):
        tg = TemporalGraph()
        r0 = 0.90
        tg.nodes["lesson:stable_pattern"] = TemporalNode(
            id="lesson:stable_pattern", resonance=r0, resting_resonance=0.50)
        tg.nodes["subconscious:reactive"] = TemporalNode(
            id="subconscious:reactive", resonance=r0, resting_resonance=0.50)

        tg.apply_decay(dt_s=600.0)

        lesson_r = tg.nodes["lesson:stable_pattern"].resonance
        sub_r    = tg.nodes["subconscious:reactive"].resonance
        self.assertGreater(lesson_r, sub_r,
                           "Lesson should decay slower than subconscious node")

    def test_stable_node_decays_slower(self):
        tg = TemporalGraph()
        tg.nodes["a"] = TemporalNode(id="a", resonance=0.85,
                                     resting_resonance=0.50, stability_bias=0.9)
        tg.nodes["b"] = TemporalNode(id="b", resonance=0.85,
                                     resting_resonance=0.50, stability_bias=0.0)
        tg.apply_decay(dt_s=300.0)
        self.assertGreater(tg.nodes["a"].resonance, tg.nodes["b"].resonance,
                           "Stable node should decay slower")


class TestInterference(unittest.TestCase):
    def test_weaker_mode_loses_more(self):
        tg = TemporalGraph()
        tg.nodes["subconscious:reactive"]     = TemporalNode(
            id="subconscious:reactive",     resonance=0.50, harmony_bonus=0.1)
        tg.nodes["subconscious:deliberative"] = TemporalNode(
            id="subconscious:deliberative", resonance=0.85, harmony_bonus=0.2)

        r_reactive_before     = tg.nodes["subconscious:reactive"].resonance
        r_deliberative_before = tg.nodes["subconscious:deliberative"].resonance

        tg.apply_interference()

        # Weaker (reactive) should lose resonance
        self.assertLess(tg.nodes["subconscious:reactive"].resonance, r_reactive_before)
        # Stronger (deliberative) should be unchanged
        self.assertAlmostEqual(
            tg.nodes["subconscious:deliberative"].resonance,
            r_deliberative_before, places=5)

    def test_no_interference_when_only_one_node(self):
        tg = TemporalGraph()
        tg.nodes["subconscious:reactive"] = TemporalNode(
            id="subconscious:reactive", resonance=0.80, harmony_bonus=0.1)
        r_before = tg.nodes["subconscious:reactive"].resonance
        tg.apply_interference()
        self.assertAlmostEqual(tg.nodes["subconscious:reactive"].resonance,
                               r_before, places=5)


class TestOrientationTrajectory(unittest.TestCase):
    def test_snapshot_recorded(self):
        tg = _graph()
        tg.record_orientation_snapshot({
            "chaos_score": 0.3, "harmony_score": 0.7,
            "drift_pressure": 0.2, "rhythm_phase": "exhale",
            "trajectory_signal": 0.8,
        })
        self.assertEqual(len(tg._orientation_history), 1)

    def test_momentum_positive_when_harmony_rises(self):
        tg = _graph()
        for i in range(12):
            tg.record_orientation_snapshot({
                "chaos_score": 0.2,
                "harmony_score": 0.3 + i * 0.04,   # rising
                "drift_pressure": 0.1,
                "rhythm_phase": "exhale",
                "trajectory_signal": 0.7,
            })
        m = tg.get_orientation_momentum()
        self.assertGreater(m["harmony_trend"], 0.0)
        self.assertGreater(m["momentum"], 0.0)

    def test_momentum_negative_when_chaos_rises(self):
        tg = _graph()
        for i in range(12):
            tg.record_orientation_snapshot({
                "chaos_score": 0.1 + i * 0.05,   # rising chaos
                "harmony_score": 0.5,
                "drift_pressure": 0.1,
                "rhythm_phase": "neutral",
                "trajectory_signal": 0.5,
            })
        m = tg.get_orientation_momentum()
        self.assertGreater(m["chaos_trend"], 0.0)
        self.assertLess(m["momentum"], 0.0)

    def test_to_orientation_signal_includes_stability_and_momentum(self):
        tg = _graph()
        sig = tg.to_orientation_signal()
        self.assertIn("stability_index", sig)
        self.assertIn("momentum", sig)


if __name__ == "__main__":
    unittest.main()
