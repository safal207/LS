# -*- coding: utf-8 -*-
"""
SystemObserver — мета-когнитивный наблюдатель за адекватностью системы.

Следит за состоянием всего когнитивного поля (TemporalGraph + 5 сил) и
применяет корректирующую Силу 6 при обнаружении патологий.

Патологии:
  OVERHEATING        — все узлы перегреты, нет дискриминации
  OSSIFICATION       — ось заморожена, система не принимает новые сигналы
  VACUUM             — нет ни одного активного узла, пустота
  SPLIT_BRAIN        — два режима в клинче, система не может выбрать
  RUNAWAY_CHAOS      — хаос нарастает лавинообразно, поле рушится
  RESONANCE_COLLAPSE — ось слишком слабая, не может направлять решения
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .temporal_graph import TemporalGraph

# ── Патологии ────────────────────────────────────────────────────────────────

OVERHEATING        = "OVERHEATING"         # среднее resonance > _OVERHEAT_MEAN
OSSIFICATION       = "OSSIFICATION"        # ось не менялась > _OSSIFY_CYCLES
VACUUM             = "VACUUM"              # max resonance < _VACUUM_THRESH
SPLIT_BRAIN        = "SPLIT_BRAIN"         # два узла вплотную на высоком резонансе
RUNAWAY_CHAOS      = "RUNAWAY_CHAOS"       # chaos_trend < _CHAOS_COLLAPSE
RESONANCE_COLLAPSE = "RESONANCE_COLLAPSE"  # resonance оси < _WEAK_AXIS

# ── Пороги ───────────────────────────────────────────────────────────────────

_OVERHEAT_MEAN   = 0.82   # среднее резонанса — перегрев
_VACUUM_THRESH   = 0.45   # максимальное резонанса — вакуум
_SPLIT_GAP       = 0.05   # разрыв между топ-2 при обоих > 0.70 — split-brain
_OSSIFY_CYCLES   = 8      # циклов без смены оси — оссификация
_OSSIFY_BIAS     = 0.80   # stability_bias оси при оссификации
_CHAOS_COLLAPSE  = -0.30  # chaos_trend — лавинный хаос
_WEAK_AXIS       = 0.35   # resonance оси — коллапс
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

# Штрафы адекватности за каждую патологию
_PATHOLOGY_DEDUCTIONS: Dict[str, float] = {
    OVERHEATING:        0.15,
    OSSIFICATION:       0.20,
    VACUUM:             0.30,
    SPLIT_BRAIN:        0.25,
    RUNAWAY_CHAOS:      0.20,
    RESONANCE_COLLAPSE: 0.25,
}


# ── Отчёт ────────────────────────────────────────────────────────────────────

@dataclass
class AdequacyReport:
    """Результат одного цикла наблюдения."""
    score: float                    # 0.0 (кризис) → 1.0 (здоровое состояние)
    pathologies: List[str]          # коды обнаруженных патологий
    corrections: List[str]          # описания применённых коррекций
    axis_id: Optional[str]          # id текущей оси
    timestamp: float = field(default_factory=time.time)

    @property
    def adequate(self) -> bool:
        """Система работает нормально."""
        return self.score >= 0.65

    @property
    def critical(self) -> bool:
        """Система в критическом состоянии."""
        return self.score < 0.40


# ── Наблюдатель ──────────────────────────────────────────────────────────────

class SystemObserver:
    """
    Мета-когнитивный наблюдатель (Сила 6).

    Запускается после всех пяти сил в каждом цикле Coordinator.decide().
    Обнаруживает патологические состояния и применяет корректирующие воздействия
    непосредственно на узлы TemporalGraph.

    Принцип: наблюдатель не вмешивается в норме — только при отклонениях.
    Его коррекции минимальны и направлены на восстановление динамического
    равновесия, а не на навязывание конкретного состояния.
    """

    def __init__(self) -> None:
        # История отчётов (последние 50 циклов)
        self._reports: deque[AdequacyReport] = deque(maxlen=50)
        # Счётчик последовательных циклов с одной и той же осью
        self._axis_tenure: Dict[str, int] = {}
        self._last_axis: Optional[str] = None
        # Feature 2: ????????????? ??????? ????????? ?? ??????
        self._pathology_counts: Dict[str, int] = {}
        # ????? N ?????????? ????????? -> ????? lesson:meta:* ????
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

    # ── Главный метод ────────────────────────────────────────────────────────

    def observe_and_correct(
        self,
        graph: "TemporalGraph",
        chaos_trend: float = 0.0,
    ) -> AdequacyReport:
        """
        1. Наблюдает текущее состояние графа → обнаруживает патологии.
        2. Применяет минимальные корректирующие силы к узлам.
        3. Вычисляет score адекватности.
        4. Сохраняет отчёт в историю.
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

        # Обновляем счётчик непрерывного владения осью
        if axis_id is not None:
            if axis_id == self._last_axis:
                self._axis_tenure[axis_id] = self._axis_tenure.get(axis_id, 0) + 1
            else:
                self._axis_tenure = {axis_id: 1}
                self._last_axis = axis_id
        else:
            self._axis_tenure = {}
            self._last_axis = None

        # ── Обнаружение патологий ─────────────────────────────────────────────

        resonances  = [n.resonance for n in nodes]
        mean_r      = sum(resonances) / len(resonances)
        max_r       = max(resonances)

        # 1. OVERHEATING: среднее выше порога → поле перегрето
        if mean_r > _OVERHEAT_MEAN:
            pathologies.append(OVERHEATING)

        # 2. VACUUM: даже лучший узел ниже порога → пустота
        if max_r < _VACUUM_THRESH:
            pathologies.append(VACUUM)

        # 3. OSSIFICATION: ось не менялась слишком долго + заморозилась
        if (
            axis_id is not None
            and self._axis_tenure.get(axis_id, 0) >= _OSSIFY_CYCLES
            and axis_node is not None
            and axis_node.stability_bias >= _OSSIFY_BIAS
        ):
            pathologies.append(OSSIFICATION)

        # 4. SPLIT_BRAIN: два верхних узла почти равны и оба высоки
        sorted_nodes = sorted(nodes, key=lambda n: n.resonance, reverse=True)
        if (
            len(sorted_nodes) >= 2
            and sorted_nodes[0].resonance > 0.70
            and sorted_nodes[1].resonance > 0.70
            and (sorted_nodes[0].resonance - sorted_nodes[1].resonance) < _SPLIT_GAP
        ):
            pathologies.append(SPLIT_BRAIN)

        # 5. RUNAWAY_CHAOS: тренд хаоса уходит в пике
        if chaos_trend < _CHAOS_COLLAPSE:
            pathologies.append(RUNAWAY_CHAOS)

        # 6. RESONANCE_COLLAPSE: ось слишком слабая
        if axis_node is not None and axis_node.resonance < _WEAK_AXIS:
            pathologies.append(RESONANCE_COLLAPSE)

        # ── Коррекции (Сила 6) ────────────────────────────────────────────────

        if OVERHEATING in pathologies:
            # Нормализуем всё поле — снижаем и resting, и текущий резонанс.
            # Нельзя использовать resting как пол: он тоже перегрет.
            for n in nodes:
                n.resting_resonance = max(0.30, n.resting_resonance * 0.88)
                n.resonance = max(n.resting_resonance, n.resonance * 0.88)
            corrections.append("normalized field ×0.88 (overheating)")

        if VACUUM in pathologies:
            # Поднимаем resting и текущий резонанс всех узлов
            for n in nodes:
                rr = n.resting_resonance if n.resting_resonance is not None else 0.5
                n.resting_resonance = min(0.65, rr + 0.10)
                n.resonance = max(n.resonance, n.resting_resonance)
            # Если нет ни одного subconscious-узла — инжектируем якорь
            has_sub = any(n.id.startswith("subconscious:") for n in nodes)
            if not has_sub:
                graph.add_or_update("subconscious:deliberative", 0.55, 0.25)
                corrections.append("injected anchor node subconscious:deliberative (vacuum)")
            corrections.append("lifted resting resonances +0.10 (vacuum)")

        if OSSIFICATION in pathologies and axis_node is not None:
            # Снижаем stability_bias + смещаем ось вниз (включая resting).
            # Ось заморожена — нужно разморозить полностью, не только current.
            axis_node.stability_bias = max(0.0, axis_node.stability_bias - 0.30)
            axis_node.resting_resonance = max(0.30, axis_node.resting_resonance - 0.08)
            axis_node.resonance = max(axis_node.resting_resonance, axis_node.resonance - 0.08)
            # Сбрасываем счётчик чтобы дать шанс другим узлам
            self._axis_tenure[axis_id] = 0
            corrections.append(
                f"de-ossified '{axis_id}': stability_bias -{0.30:.2f}, nudge -0.08"
            )

        if SPLIT_BRAIN in pathologies and len(sorted_nodes) >= 2:
            weaker = sorted_nodes[1]
            # Используем фиксированный нижний пол (не resting — он тоже высокий при split).
            weaker.resonance = max(0.30, weaker.resonance - 0.12)
            corrections.append(
                f"resolved split-brain: suppressed '{weaker.id}' by 0.12"
            )

        if RUNAWAY_CHAOS in pathologies and axis_node is not None:
            # Усиливаем якорную ось как противовес хаосу
            axis_node.resonance = min(1.0, axis_node.resonance + 0.08)
            if axis_node.resting_resonance is not None:
                axis_node.resting_resonance = min(0.80, axis_node.resting_resonance + 0.05)
            corrections.append(f"chaos anchor: boosted '{axis_id}' +0.08 (runaway_chaos)")

        if RESONANCE_COLLAPSE in pathologies and axis_node is not None:
            # Экстренный буст оси
            axis_node.resonance = min(1.0, axis_node.resonance + 0.15)
            corrections.append(f"emergency boost +0.15 for '{axis_id}' (resonance_collapse)")

        # ── Score ─────────────────────────────────────────────────────────────

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

        # Feature 2: записываем meta-уроки при повторных патологиях
        self._maybe_write_meta_lessons(graph, pathologies)

        return report

    # ── Feature 2: Мета-уроки наблюдателя ────────────────────────────────────

    def _maybe_write_meta_lessons(
        self, graph: "TemporalGraph", pathologies: List[str]
    ) -> None:
        """
        Если одна и та же патология встречается >= _meta_lesson_threshold раз,
        наблюдатель записывает lesson:meta:* узел в TemporalGraph.
        Система запоминает собственные паттерны слабостей.
        """
        for p in pathologies:
            self._pathology_counts[p] = self._pathology_counts.get(p, 0) + 1
            count = self._pathology_counts[p]
            if count == self._meta_lesson_threshold:
                node_id = f"lesson:meta:{p.lower()}_pattern"
                # resonance зависит от серьёзности патологии
                severity = _PATHOLOGY_DEDUCTIONS.get(p, 0.10)
                resonance = round(min(0.80, 0.45 + severity * 1.5), 3)
                graph.add_or_update(node_id, resonance, harmony_bonus=0.20)

    # ── Feature 6: Ночной отчёт сессии ───────────────────────────────────────

    def session_report(self, graph: "TemporalGraph") -> dict:
        """
        Итоговый анализ сессии. Вызывается при sleep consolidation.
        - Классифицирует качество сессии (лёгкая / умеренная / тяжёлая)
        - Инжектирует lesson:session:* узлы для доминирующих патологий
        - Возвращает dict для логирования/observability
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

    # ── Аналитика ─────────────────────────────────────────────────────────────

    def adequacy_trend(self) -> float:
        """
        Тренд адекватности за последние N отчётов.
        Положительный → улучшение, отрицательный → деградация.
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
