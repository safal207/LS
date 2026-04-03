# -*- coding: utf-8 -*-
"""
Тесты SystemObserver — мета-когнитивного наблюдателя (Сила 6).

Запуск: python3 tests/unit/test_system_observer.py
"""

import sys
import os
import unittest
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../python/modules"))

from hexagon_core.temporal_graph import TemporalGraph, TemporalNode
from hexagon_core.system_observer import (
    SystemObserver,
    AdequacyReport,
    OVERHEATING,
    OSSIFICATION,
    VACUUM,
    SPLIT_BRAIN,
    RUNAWAY_CHAOS,
    RESONANCE_COLLAPSE,
)


def _graph_with_nodes(specs: list) -> TemporalGraph:
    """Создаёт граф с заданными узлами: [(id, resonance, harmony), ...]"""
    g = TemporalGraph()
    for item in specs:
        nid, res = item[0], item[1]
        harm = item[2] if len(item) > 2 else 0.3
        g.nodes[nid] = TemporalNode(id=nid, resonance=res, harmony_bonus=harm)
    return g


class TestAdequacyReportProperties(unittest.TestCase):
    """AdequacyReport.adequate / critical пороги."""

    def test_score_1_is_adequate(self):
        r = AdequacyReport(score=1.0, pathologies=[], corrections=[], axis_id=None)
        self.assertTrue(r.adequate)
        self.assertFalse(r.critical)

    def test_score_0_65_boundary(self):
        r = AdequacyReport(score=0.65, pathologies=[], corrections=[], axis_id=None)
        self.assertTrue(r.adequate)

    def test_score_0_64_not_adequate(self):
        r = AdequacyReport(score=0.64, pathologies=[], corrections=[], axis_id=None)
        self.assertFalse(r.adequate)

    def test_score_below_40_is_critical(self):
        r = AdequacyReport(score=0.39, pathologies=[], corrections=[], axis_id=None)
        self.assertTrue(r.critical)

    def test_score_40_not_critical(self):
        r = AdequacyReport(score=0.40, pathologies=[], corrections=[], axis_id=None)
        self.assertFalse(r.critical)


class TestDetectOverheating(unittest.TestCase):
    """OVERHEATING: среднее resonance > 0.82."""

    def test_detects_overheating(self):
        g = _graph_with_nodes([
            ("subconscious:a", 0.90),
            ("subconscious:b", 0.88),
            ("subconscious:c", 0.85),
        ])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertIn(OVERHEATING, report.pathologies)

    def test_no_overheating_normal_field(self):
        g = _graph_with_nodes([
            ("subconscious:a", 0.75),
            ("subconscious:b", 0.60),
            ("subconscious:c", 0.55),
        ])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertNotIn(OVERHEATING, report.pathologies)

    def test_overheating_normalizes_field(self):
        g = _graph_with_nodes([
            ("subconscious:a", 0.92),
            ("subconscious:b", 0.90),
        ])
        obs = SystemObserver()
        obs.observe_and_correct(g)
        # После коррекции все узлы должны быть ниже исходных значений
        for n in g.nodes.values():
            self.assertLess(n.resonance, 0.92)

    def test_overheating_correction_in_report(self):
        g = _graph_with_nodes([("a", 0.95), ("b", 0.93)])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertTrue(any("normalized" in c for c in report.corrections))


class TestDetectVacuum(unittest.TestCase):
    """VACUUM: max resonance < 0.45."""

    def test_detects_vacuum(self):
        g = _graph_with_nodes([
            ("subconscious:a", 0.30),
            ("subconscious:b", 0.25),
        ])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertIn(VACUUM, report.pathologies)

    def test_vacuum_lifts_resting_resonance(self):
        g = _graph_with_nodes([("subconscious:a", 0.30)])
        g.nodes["subconscious:a"].resting_resonance = 0.30
        obs = SystemObserver()
        obs.observe_and_correct(g)
        self.assertGreater(g.nodes["subconscious:a"].resting_resonance, 0.30)

    def test_vacuum_injects_anchor_when_no_subconscious(self):
        g = _graph_with_nodes([("lesson:x", 0.25)])
        obs = SystemObserver()
        obs.observe_and_correct(g)
        # Должен инжектировать якорный subconscious-узел
        self.assertIn("subconscious:deliberative", g.nodes)

    def test_vacuum_no_inject_if_subconscious_exists(self):
        g = _graph_with_nodes([("subconscious:reactive", 0.30)])
        obs = SystemObserver()
        obs.observe_and_correct(g)
        # Не должен добавить ещё один
        sub_count = sum(1 for nid in g.nodes if nid.startswith("subconscious:"))
        self.assertEqual(sub_count, 1)


class TestDetectOssification(unittest.TestCase):
    """OSSIFICATION: ось не менялась >= 8 циклов и stability_bias >= 0.80."""

    def _run_n_cycles(self, g, n):
        obs = SystemObserver()
        report = None
        for _ in range(n):
            report = obs.observe_and_correct(g)
        return obs, report

    def test_detects_ossification_after_8_cycles(self):
        g = _graph_with_nodes([("subconscious:deliberative", 0.85, 0.40)])
        g.nodes["subconscious:deliberative"].stability_bias = 0.85

        obs = SystemObserver()
        # Первые 7 циклов — ещё не патология
        for _ in range(7):
            r = obs.observe_and_correct(g)
            self.assertNotIn(OSSIFICATION, r.pathologies)

        # 8-й цикл → патология
        r = obs.observe_and_correct(g)
        self.assertIn(OSSIFICATION, r.pathologies)

    def test_ossification_reduces_stability_bias(self):
        g = _graph_with_nodes([("subconscious:deliberative", 0.85, 0.40)])
        g.nodes["subconscious:deliberative"].stability_bias = 0.90
        obs, _ = self._run_n_cycles(g, 8)
        self.assertLess(g.nodes["subconscious:deliberative"].stability_bias, 0.90)

    def test_ossification_nudges_resonance_down(self):
        g = _graph_with_nodes([("subconscious:deliberative", 0.90, 0.40)])
        g.nodes["subconscious:deliberative"].stability_bias = 0.85
        resonance_before = g.nodes["subconscious:deliberative"].resonance
        obs, _ = self._run_n_cycles(g, 8)
        self.assertLess(
            g.nodes["subconscious:deliberative"].resonance,
            resonance_before,
        )

    def test_no_ossification_low_stability_bias(self):
        g = _graph_with_nodes([("subconscious:deliberative", 0.85)])
        g.nodes["subconscious:deliberative"].stability_bias = 0.50  # ниже порога
        obs, report = self._run_n_cycles(g, 10)
        self.assertNotIn(OSSIFICATION, report.pathologies)


class TestDetectSplitBrain(unittest.TestCase):
    """SPLIT_BRAIN: два узла > 0.70 с разницей < 0.05."""

    def test_detects_split_brain(self):
        g = _graph_with_nodes([
            ("subconscious:reactive",    0.82),
            ("subconscious:deliberative", 0.80),
        ])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertIn(SPLIT_BRAIN, report.pathologies)

    def test_no_split_brain_large_gap(self):
        g = _graph_with_nodes([
            ("subconscious:reactive",    0.85),
            ("subconscious:deliberative", 0.70),  # разрыв 0.15 > 0.05
        ])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertNotIn(SPLIT_BRAIN, report.pathologies)

    def test_split_brain_suppresses_weaker(self):
        g = _graph_with_nodes([
            ("subconscious:reactive",    0.82),
            ("subconscious:deliberative", 0.80),
        ])
        obs = SystemObserver()
        obs.observe_and_correct(g)
        # Более слабый узел должен потерять резонанс
        self.assertLess(g.nodes["subconscious:deliberative"].resonance, 0.80)

    def test_split_brain_dominant_unchanged(self):
        g = _graph_with_nodes([
            ("subconscious:reactive",    0.82),
            ("subconscious:deliberative", 0.80),
        ])
        obs = SystemObserver()
        obs.observe_and_correct(g)
        # Доминирующий не должен быть подавлен (только OVERHEATING мог бы его снизить)
        self.assertGreaterEqual(g.nodes["subconscious:reactive"].resonance, 0.80)


class TestDetectRunawayChaos(unittest.TestCase):
    """RUNAWAY_CHAOS: chaos_trend < -0.30."""

    def test_detects_runaway_chaos(self):
        g = _graph_with_nodes([("subconscious:a", 0.65)])
        obs = SystemObserver()
        report = obs.observe_and_correct(g, chaos_trend=-0.35)
        self.assertIn(RUNAWAY_CHAOS, report.pathologies)

    def test_no_runaway_chaos_mild_trend(self):
        g = _graph_with_nodes([("subconscious:a", 0.65)])
        obs = SystemObserver()
        report = obs.observe_and_correct(g, chaos_trend=-0.15)
        self.assertNotIn(RUNAWAY_CHAOS, report.pathologies)

    def test_runaway_chaos_boosts_axis(self):
        g = _graph_with_nodes([("subconscious:deliberative", 0.65, 0.40)])
        before = g.nodes["subconscious:deliberative"].resonance
        obs = SystemObserver()
        obs.observe_and_correct(g, chaos_trend=-0.40)
        self.assertGreater(
            g.nodes["subconscious:deliberative"].resonance, before
        )


class TestDetectResonanceCollapse(unittest.TestCase):
    """RESONANCE_COLLAPSE: resonance оси < 0.35."""

    def test_detects_collapse(self):
        g = _graph_with_nodes([("subconscious:a", 0.28)])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertIn(RESONANCE_COLLAPSE, report.pathologies)

    def test_collapse_emergency_boost(self):
        g = _graph_with_nodes([("subconscious:a", 0.28)])
        obs = SystemObserver()
        obs.observe_and_correct(g)
        self.assertGreater(g.nodes["subconscious:a"].resonance, 0.28)


class TestAdequacyScore(unittest.TestCase):
    """Итоговый score снижается при патологиях, максимален при здоровом поле."""

    def test_healthy_field_score_1(self):
        g = _graph_with_nodes([
            ("subconscious:deliberative", 0.72, 0.35),
            ("lesson:analysis", 0.60, 0.20),
        ])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertEqual(report.score, 1.0)
        self.assertTrue(report.adequate)
        self.assertFalse(report.critical)

    def test_score_decreases_per_pathology(self):
        g = _graph_with_nodes([("subconscious:a", 0.95), ("subconscious:b", 0.92)])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertLess(report.score, 1.0)

    def test_two_pathologies_lower_score(self):
        # Оба перегрев И split-brain
        g = _graph_with_nodes([
            ("subconscious:a", 0.91),
            ("subconscious:b", 0.90),
        ])
        obs = SystemObserver()
        report = obs.observe_and_correct(g)
        self.assertLess(report.score, 0.85)  # min два штрафа: 0.15 + 0.25

    def test_score_clamped_to_zero_not_negative(self):
        # Куча патологий одновременно → score не уходит ниже 0
        g = _graph_with_nodes([("subconscious:a", 0.90), ("subconscious:b", 0.89)])
        obs = SystemObserver()
        report = obs.observe_and_correct(g, chaos_trend=-0.5)
        self.assertGreaterEqual(report.score, 0.0)


class TestAdequacyTrend(unittest.TestCase):
    """adequacy_trend() отражает динамику здоровья системы."""

    def test_trend_zero_insufficient_data(self):
        obs = SystemObserver()
        self.assertEqual(obs.adequacy_trend(), 0.0)

    def test_positive_trend_when_improving(self):
        obs = SystemObserver()
        # Добавляем плохие отчёты, потом хорошие
        for score in [0.40, 0.45, 0.50, 0.80, 0.85, 0.90, 0.95, 1.0]:
            obs._reports.append(
                AdequacyReport(score=score, pathologies=[], corrections=[], axis_id="x")
            )
        self.assertGreater(obs.adequacy_trend(), 0.0)

    def test_negative_trend_when_degrading(self):
        obs = SystemObserver()
        for score in [0.90, 0.85, 0.80, 0.50, 0.45, 0.40, 0.35, 0.30]:
            obs._reports.append(
                AdequacyReport(score=score, pathologies=[], corrections=[], axis_id="x")
            )
        self.assertLess(obs.adequacy_trend(), 0.0)


class TestStats(unittest.TestCase):
    """stats() возвращает корректную структуру."""

    def test_stats_no_history_defaults(self):
        obs = SystemObserver()
        s = obs.stats()
        self.assertEqual(s["score"], 1.0)
        self.assertTrue(s["adequate"])
        self.assertEqual(s["total_reports"], 0)

    def test_stats_after_observation(self):
        g = _graph_with_nodes([("subconscious:a", 0.70)])
        obs = SystemObserver()
        obs.observe_and_correct(g)
        s = obs.stats()
        self.assertEqual(s["total_reports"], 1)
        self.assertIn("score", s)
        self.assertIn("pathologies", s)
        self.assertIn("axis_id", s)
        self.assertIn("axis_tenure", s)
        self.assertIn("trend", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
