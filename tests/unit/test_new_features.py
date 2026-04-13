# -*- coding: utf-8 -*-
"""
Тесты для шести новых фич когнитивного поля.

Запуск: python3 tests/unit/test_new_features.py
"""

import sys
import os
import unittest
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../python/modules"))

from hexagon_core.temporal_graph import TemporalGraph, TemporalNode
from hexagon_core.system_observer import SystemObserver, OSSIFICATION, OVERHEATING
from hexagon_core.user_profile import UserProfileStore, UserSession


# ═══════════════════════════════════════════════════════════════════════
# Feature 1 (Codex) + наши методы: причинный граф
# ═══════════════════════════════════════════════════════════════════════

class TestCausalGraph(unittest.TestCase):
    """link_nodes / get_linked_nodes / apply_association_boost."""

    def _graph(self):
        g = TemporalGraph()
        g.nodes["a"] = TemporalNode(id="a", resonance=0.80, harmony_bonus=0.3)
        g.nodes["b"] = TemporalNode(id="b", resonance=0.50, harmony_bonus=0.3)
        g.nodes["c"] = TemporalNode(id="c", resonance=0.40, harmony_bonus=0.3)
        g.links["a"] = {}
        g.links["b"] = {}
        g.links["c"] = {}
        return g

    def test_link_nodes_creates_bidirectional_edge(self):
        g = self._graph()
        g.link_nodes("a", "b", weight=0.25)
        self.assertIn("b", g.links["a"])
        self.assertIn("a", g.links["b"])
        self.assertAlmostEqual(g.links["a"]["b"], 0.25)

    def test_link_nodes_unidirectional(self):
        g = self._graph()
        g.link_nodes("a", "b", weight=0.20, bidirectional=False)
        self.assertIn("b", g.links["a"])
        self.assertNotIn("a", g.links.get("b", {}))

    def test_get_linked_nodes_sorted_by_weight(self):
        g = self._graph()
        g.link_nodes("a", "b", weight=0.10)
        g.link_nodes("a", "c", weight=0.30)
        linked = g.get_linked_nodes("a")
        self.assertEqual(linked[0][0], "c")  # strongest first
        self.assertEqual(linked[1][0], "b")

    def test_apply_association_boost_active_node_boosts_linked(self):
        g = self._graph()
        g.link_nodes("a", "b", weight=0.50)
        b_before = g.nodes["b"].resonance
        deltas = g.apply_association_boost(threshold=0.72, boost_factor=0.07)
        self.assertIn("b", deltas)
        self.assertGreater(g.nodes["b"].resonance, b_before)

    def test_apply_association_boost_inactive_node_no_boost(self):
        g = self._graph()
        g.link_nodes("c", "b", weight=0.50)  # c.resonance=0.40 < threshold 0.72
        b_before = g.nodes["b"].resonance
        g.apply_association_boost(threshold=0.72)
        self.assertEqual(g.nodes["b"].resonance, b_before)

    def test_apply_association_boost_no_links_no_deltas(self):
        g = TemporalGraph()
        g.nodes["x"] = TemporalNode(id="x", resonance=0.90)
        g.links["x"] = {}
        deltas = g.apply_association_boost()
        self.assertEqual(deltas, {})

    def test_prune_weak_nodes_cleans_up_links(self):
        g = self._graph()
        g.link_nodes("a", "b", weight=0.20)
        g.nodes["b"].resonance = 0.10  # below prune threshold
        g.prune_weak_nodes(threshold=0.20)
        self.assertNotIn("b", g.nodes)
        # link from a to b should be gone
        self.assertNotIn("b", g.links.get("a", {}))


# ═══════════════════════════════════════════════════════════════════════
# Feature 3: Предиктивная ось
# ═══════════════════════════════════════════════════════════════════════

class TestPredictiveAxis(unittest.TestCase):

    def test_empty_graph_returns_none(self):
        g = TemporalGraph()
        self.assertIsNone(g.predictive_axis())

    def test_fast_growing_node_wins_at_horizon(self):
        g = TemporalGraph()
        # Node A: high resonance, zero velocity
        g.nodes["stable"] = TemporalNode(id="stable", resonance=0.80)
        g.nodes["stable"].velocity = 0.0
        # Node B: lower resonance but growing fast
        g.nodes["rising"] = TemporalNode(id="rising", resonance=0.50)
        g.nodes["rising"].velocity = 0.008  # +0.008/s × 60s = +0.48 projected
        axis = g.predictive_axis(horizon_s=60.0)
        self.assertEqual(axis.id, "rising")

    def test_current_axis_wins_at_zero_horizon(self):
        g = TemporalGraph()
        g.nodes["stable"] = TemporalNode(id="stable", resonance=0.85)
        g.nodes["rising"] = TemporalNode(id="rising", resonance=0.50)
        g.nodes["rising"].velocity = 0.01
        axis = g.predictive_axis(horizon_s=0.0)
        self.assertEqual(axis.id, "stable")

    def test_predicted_axis_in_orientation_signal(self):
        g = TemporalGraph()
        g.nodes["a"] = TemporalNode(id="a", resonance=0.70)
        signal = g.to_orientation_signal()
        self.assertIn("predicted_axis_id", signal)
        self.assertIn("predicted_axis_resonance", signal)
        self.assertEqual(signal["predicted_axis_id"], "a")

    def test_orientation_signal_empty_graph_has_predicted_fields(self):
        g = TemporalGraph()
        signal = g.to_orientation_signal()
        self.assertEqual(signal["predicted_axis_id"], "")
        self.assertEqual(signal["predicted_axis_resonance"], 0.0)


# ═══════════════════════════════════════════════════════════════════════
# Feature 2: Observer — мета-уроки при повторных патологиях
# ═══════════════════════════════════════════════════════════════════════

class TestObserverMetaLessons(unittest.TestCase):

    def _overheated_graph(self):
        g = TemporalGraph()
        for i, r in enumerate([0.90, 0.88, 0.86]):
            g.nodes[f"subconscious:mode{i}"] = TemporalNode(
                id=f"subconscious:mode{i}", resonance=r
            )
        return g

    def test_no_meta_lesson_before_threshold(self):
        obs = SystemObserver()
        for _ in range(2):  # threshold=3, only 2 cycles
            obs.observe_and_correct(self._overheated_graph())
        # Check internal counter — should be 2, not yet at threshold
        self.assertEqual(obs._pathology_counts.get("OVERHEATING", 0), 2)

    def test_meta_lesson_injected_at_threshold(self):
        obs = SystemObserver()
        last_g = None
        for _ in range(3):
            last_g = self._overheated_graph()
            obs.observe_and_correct(last_g)
        # On 3rd cycle the lesson should be injected into last_g
        lesson_keys = [k for k in last_g.nodes if k.startswith("lesson:meta:")]
        self.assertGreater(len(lesson_keys), 0)
        self.assertTrue(any("overheating" in k for k in lesson_keys))

    def test_meta_lesson_reasonable_resonance(self):
        obs = SystemObserver()
        last_g = None
        for _ in range(3):
            last_g = self._overheated_graph()
            obs.observe_and_correct(last_g)
        for k, n in last_g.nodes.items():
            if k.startswith("lesson:meta:"):
                self.assertGreater(n.resonance, 0.40)
                self.assertLessEqual(n.resonance, 0.80)

    def test_meta_lesson_count_correct_after_many_cycles(self):
        obs = SystemObserver()
        for _ in range(6):
            obs.observe_and_correct(self._overheated_graph())
        # Threshold=3 reached once — count should be 6, node injected once
        self.assertEqual(obs._pathology_counts.get("OVERHEATING", 0), 6)


# ═══════════════════════════════════════════════════════════════════════
# Feature 4: UserProfileStore
# ═══════════════════════════════════════════════════════════════════════

class TestUserProfileStore(unittest.TestCase):

    def test_no_hint_before_min_turns(self):
        store = UserProfileStore()
        for _ in range(4):  # MIN_TURNS = 5
            store.record_turn("u1", "deliberative")
        self.assertIsNone(store.get_starting_hint("u1"))

    def test_hint_returns_dominant_mode(self):
        store = UserProfileStore()
        for _ in range(8):
            store.record_turn("u1", "deliberative")
        for _ in range(2):
            store.record_turn("u1", "creative")
        self.assertEqual(store.get_starting_hint("u1"), "deliberative")

    def test_hint_reflects_recent_shift(self):
        store = UserProfileStore()
        # First 8 turns: deliberative (history)
        for _ in range(8):
            store.record_turn("u1", "deliberative")
        # Last 20 turns: creative (recent window)
        for _ in range(20):
            store.record_turn("u1", "creative")
        # recent_dominant_mode should be creative now
        hint = store.get_starting_hint("u1")
        self.assertEqual(hint, "creative")

    def test_unknown_user_no_hint(self):
        store = UserProfileStore()
        self.assertIsNone(store.get_starting_hint("ghost"))

    def test_confidence_zero_insufficient_data(self):
        store = UserProfileStore()
        store.record_turn("u1", "reactive")
        self.assertEqual(store.get_confidence("u1"), 0.0)

    def test_confidence_high_single_mode(self):
        store = UserProfileStore()
        for _ in range(10):
            store.record_turn("u1", "deliberative")
        self.assertGreater(store.get_confidence("u1"), 0.8)

    def test_profile_summary_structure(self):
        store = UserProfileStore()
        for _ in range(6):
            store.record_turn("u2", "creative")
        s = store.profile_summary("u2")
        self.assertTrue(s["known"])
        self.assertEqual(s["turn_count"], 6)
        self.assertIn("dominant_mode", s)
        self.assertIn("confidence", s)
        self.assertIn("mode_counts", s)

    def test_unknown_user_profile_summary(self):
        store = UserProfileStore()
        s = store.profile_summary("nobody")
        self.assertFalse(s["known"])

    def test_multiple_users_isolated(self):
        store = UserProfileStore()
        for _ in range(6):
            store.record_turn("alice", "deliberative")
        for _ in range(6):
            store.record_turn("bob", "reactive")
        self.assertEqual(store.get_starting_hint("alice"), "deliberative")
        self.assertEqual(store.get_starting_hint("bob"), "reactive")

    def test_persist_and_load(self):
        import tempfile
        store = UserProfileStore()
        for _ in range(10):
            store.record_turn("u1", "deliberative")
        for _ in range(5):
            store.record_turn("u2", "creative")

        summary_1_before = store.profile_summary("u1")
        summary_2_before = store.profile_summary("u2")

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            store.persist(tmp_path)
            new_store = UserProfileStore()
            new_store.load(tmp_path)

            self.assertEqual(new_store.profile_summary("u1"), summary_1_before)
            self.assertEqual(new_store.profile_summary("u2"), summary_2_before)
            self.assertEqual(len(new_store._profiles["u2"].recent_modes), 5)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


# ═══════════════════════════════════════════════════════════════════════
# Feature 6: Session report
# ═══════════════════════════════════════════════════════════════════════

class TestSessionReport(unittest.TestCase):

    def _overheated_graph(self):
        g = TemporalGraph()
        for i, r in enumerate([0.90, 0.88]):
            g.nodes[f"subconscious:m{i}"] = TemporalNode(
                id=f"subconscious:m{i}", resonance=r
            )
        return g

    def test_empty_observer_returns_no_data(self):
        obs = SystemObserver()
        g = TemporalGraph()
        result = obs.session_report(g)
        self.assertEqual(result.get("total_cycles", 0), 0)

    def test_session_quality_easy_when_high_scores(self):
        obs = SystemObserver()
        from hexagon_core.system_observer import AdequacyReport
        for _ in range(5):
            obs._reports.append(
                AdequacyReport(score=0.92, pathologies=[], corrections=[], axis_id="x")
            )
        g = TemporalGraph()
        result = obs.session_report(g)
        self.assertEqual(result["session_quality"], "лёгкая")

    def test_session_quality_heavy_when_low_scores(self):
        obs = SystemObserver()
        from hexagon_core.system_observer import AdequacyReport
        for _ in range(5):
            obs._reports.append(
                AdequacyReport(score=0.45, pathologies=[OVERHEATING], corrections=[], axis_id="x")
            )
        g = TemporalGraph()
        result = obs.session_report(g)
        self.assertEqual(result["session_quality"], "тяжёлая")

    def test_session_report_injects_lesson_nodes(self):
        obs = SystemObserver()
        # Use fresh graph each cycle so OVERHEATING keeps occurring
        for _ in range(3):
            obs.observe_and_correct(self._overheated_graph())
        result_g = self._overheated_graph()
        result = obs.session_report(result_g)
        injected = result.get("lesson_nodes_injected", [])
        # 3 occurrences of OVERHEATING → count >= 2, should inject lesson
        self.assertTrue(any("overheating" in k for k in injected))

    def test_session_report_pathology_counts(self):
        obs = SystemObserver()
        for _ in range(4):
            obs.observe_and_correct(self._overheated_graph())
        result = obs.session_report(TemporalGraph())
        counts = result.get("pathology_counts", {})
        self.assertIn(OVERHEATING, counts)
        self.assertGreaterEqual(counts[OVERHEATING], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
