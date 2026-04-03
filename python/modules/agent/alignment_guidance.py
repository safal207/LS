from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class AlignmentGuidanceMetrics:
    calls_total: int = 0
    nonempty_total: int = 0
    total_lines: int = 0
    hotspot_guidance_total: int = 0
    mismatch_guidance_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        average_lines = (
            round(self.total_lines / self.nonempty_total, 3)
            if self.nonempty_total
            else 0.0
        )
        return {
            "calls_total": self.calls_total,
            "nonempty_total": self.nonempty_total,
            "average_lines": average_lines,
            "hotspot_guidance_total": self.hotspot_guidance_total,
            "mismatch_guidance_total": self.mismatch_guidance_total,
        }


class _AlignmentGuidanceRuntime:
    def __init__(self) -> None:
        self._metrics = AlignmentGuidanceMetrics()
        self._lock = Lock()

    def record(self, *, line_count: int, hotspot_signal: bool, mismatch_signal: bool) -> None:
        with self._lock:
            self._metrics.calls_total += 1
            if line_count > 0:
                self._metrics.nonempty_total += 1
                self._metrics.total_lines += line_count
            if hotspot_signal:
                self._metrics.hotspot_guidance_total += 1
            if mismatch_signal:
                self._metrics.mismatch_guidance_total += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._metrics.to_dict()

    def reset(self) -> None:
        with self._lock:
            self._metrics = AlignmentGuidanceMetrics()


_RUNTIME = _AlignmentGuidanceRuntime()


def _normalize_report(alignment_report: dict[str, Any] | Any | None) -> dict[str, Any]:
    if alignment_report is None:
        return {}
    if isinstance(alignment_report, dict):
        return dict(alignment_report)
    if hasattr(alignment_report, "to_dict"):
        report = alignment_report.to_dict()
        if isinstance(report, dict):
            return report
    return {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def build_alignment_guidance(alignment_report: dict[str, Any] | Any | None) -> list[str]:
    report = _normalize_report(alignment_report)
    hotspots = report.get("pairwise_hotspots") or []
    mismatch_reasons = report.get("mismatch_reasons") or []
    tension_score = _safe_float(report.get("tension_score"))

    hotspot_signal = bool(hotspots)
    mismatch_signal = bool(mismatch_reasons)
    softening_signal = bool(report.get("requires_softening")) or tension_score >= 0.6
    clarification_signal = bool(report.get("requires_clarification"))
    grounding_signal = bool(report.get("requires_grounding"))

    has_signal = hotspot_signal or mismatch_signal or softening_signal or clarification_signal or grounding_signal
    if not has_signal:
        _RUNTIME.record(line_count=0, hotspot_signal=False, mismatch_signal=False)
        return []

    guidance: list[str] = []
    if hotspot_signal or softening_signal:
        guidance.append("Сначала признай напряжение и различие восприятия, затем переходи к сути.")
        guidance.append("Снизь темп ответа: короткие формулировки, без эскалации и категоричности.")

    if mismatch_signal or clarification_signal:
        guidance.append("Описывай конфликт как mismatch контекста/целей, а не как борьбу сторон.")
        guidance.append("Отделяй фоновые причины от наблюдаемого поведения и фактов диалога.")

    guidance.append("Сначала синхронизируй позиции участников, затем предлагай следующий шаг решения.")

    if grounding_signal:
        guidance.append("Не выдумывай мотивы; опирайся только на явные сигналы из текущего запроса.")

    deduped = list(dict.fromkeys(guidance))[:5]
    _RUNTIME.record(
        line_count=len(deduped),
        hotspot_signal=hotspot_signal,
        mismatch_signal=mismatch_signal,
    )
    return deduped


def get_alignment_guidance_metrics() -> dict[str, Any]:
    return _RUNTIME.snapshot()


def reset_alignment_guidance_metrics() -> None:
    _RUNTIME.reset()


__all__ = [
    "AlignmentGuidanceMetrics",
    "build_alignment_guidance",
    "get_alignment_guidance_metrics",
    "reset_alignment_guidance_metrics",
]
