"""SmartEar online metrics — rolling window tracker + drift detection.

Tracks every SelectionStage decision in memory.  Provides a ``get_dashboard()``
snapshot for monitoring and detects model drift automatically.

Drift triggers:
* Rolling average model confidence drops below ``drift_confidence_floor``.
* User feedback rate spikes (humans keep correcting the model).
* Uncertain zone rate exceeds ``drift_uncertain_rate`` — the model is
  refusing to commit too often.

When drift is detected, ``is_drifted`` becomes ``True`` and the decision model
is flagged for fallback until a retrain completes.

Usage::

    from smart_ear.metrics import SmartEarMetrics

    metrics = SmartEarMetrics(window=200, drift_confidence_floor=0.55)

    # In SelectionStage:
    metrics.record(
        source="phonetic_ml",
        model_confidence=0.82,
        calibrated_confidence=0.76,
        decision_zone="ml_strong_correct",
        was_corrected=True,
    )

    # Anywhere for monitoring:
    print(metrics.get_dashboard())

    # In SelectionStage before deciding:
    if metrics.is_drifted:
        # force heuristic fallback
"""

from __future__ import annotations

import collections
import logging
import math
import threading
import time
from typing import Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class SmartEarMetrics:
    """Thread-safe rolling metrics tracker.

    Parameters
    ----------
    window:
        Number of decisions to keep in the rolling window (default 200).
    drift_confidence_floor:
        Minimum acceptable rolling average of ``model_confidence``.
        If the rolling average falls below this, drift is flagged (default 0.45).
    drift_feedback_rate:
        If the rolling fraction of user-feedback-corrected decisions exceeds
        this, drift is flagged (default 0.30 = 30 %).
    drift_uncertain_rate:
        If the fraction of decisions landing in "uncertain" zone exceeds this,
        drift is flagged (default 0.50 = 50 %).
    """

    def __init__(
        self,
        window: int = 200,
        drift_confidence_floor: float = 0.45,
        drift_feedback_rate: float = 0.30,
        drift_uncertain_rate: float = 0.50,
    ) -> None:
        self.window = window
        self.drift_confidence_floor = drift_confidence_floor
        self.drift_feedback_rate = drift_feedback_rate
        self.drift_uncertain_rate = drift_uncertain_rate

        # Rolling deques — each element is a float or str or bool
        self._confidences: Deque[float] = collections.deque(maxlen=window)
        self._calibrated_confidences: Deque[float] = collections.deque(maxlen=window)
        self._sources: Deque[str] = collections.deque(maxlen=window)
        self._zones: Deque[str] = collections.deque(maxlen=window)
        self._feedback_flags: Deque[bool] = collections.deque(maxlen=window)

        # Counters (all-time, not windowed)
        self._total_decisions = 0
        self._total_ml_decisions = 0
        self._total_heuristic_decisions = 0
        self._total_feedback = 0

        # Zone counters (all-time)
        self._total_ml_strong_correct = 0
        self._total_ml_strong_original = 0
        self._total_uncertain = 0

        self._drift_detected = False
        self._drift_reason: Optional[str] = None
        self._last_drift_check = 0.0
        self._drift_check_interval = 10.0  # seconds

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        source: str,
        model_confidence: float = 0.0,
        calibrated_confidence: Optional[float] = None,
        decision_zone: str = "uncertain",
        is_feedback: bool = False,
    ) -> None:
        """Record one SelectionStage decision.

        Parameters
        ----------
        source:
            ``"original"``, ``"phonetic"``, ``"phonetic_ml"``, etc.
        model_confidence:
            Raw probability returned by the model (0 if heuristic used).
        calibrated_confidence:
            Calibrated probability (falls back to model_confidence if None).
        decision_zone:
            One of ``"ml_strong_correct"``, ``"ml_strong_original"``,
            ``"uncertain"``.
        is_feedback:
            True when this decision was triggered by ``user_feedback()``,
            meaning the human disagreed with the system's prior choice.
        """
        if calibrated_confidence is None:
            calibrated_confidence = model_confidence

        log_msg: Optional[str] = None
        log_level = "warning"

        with self._lock:
            self._confidences.append(model_confidence)
            self._calibrated_confidences.append(calibrated_confidence)
            self._sources.append(source)
            self._zones.append(decision_zone)
            self._feedback_flags.append(is_feedback)

            self._total_decisions += 1
            if "ml" in source:
                self._total_ml_decisions += 1
            else:
                self._total_heuristic_decisions += 1
            if is_feedback:
                self._total_feedback += 1

            # Zone counters
            if decision_zone == "ml_strong_correct":
                self._total_ml_strong_correct += 1
            elif decision_zone == "ml_strong_original":
                self._total_ml_strong_original += 1
            else:
                self._total_uncertain += 1

            now = time.monotonic()
            if now - self._last_drift_check >= self._drift_check_interval:
                self._last_drift_check = now
                log_msg, log_level = self._check_drift()

        # I/O outside the lock — avoids holding the lock during logging
        if log_msg:
            if log_level == "warning":
                logger.warning("SmartEarMetrics: %s", log_msg)
            else:
                logger.info("SmartEarMetrics: %s", log_msg)

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def _check_drift(self) -> tuple:
        """Called under lock — updates _drift_detected.

        Returns ``(message, level)`` for the caller to log *outside* the lock,
        avoiding I/O inside a critical section.  Returns ``(None, None)`` when
        there is nothing to log.
        """
        n = len(self._confidences)
        if n < 20:
            return None, None

        # 1. ML confidence floor
        ml_confs = [c for c, s in zip(self._confidences, self._sources) if "ml" in s]
        if len(ml_confs) >= 10:
            avg_conf = sum(ml_confs) / len(ml_confs)
            if avg_conf < self.drift_confidence_floor:
                self._drift_detected = True
                self._drift_reason = (
                    f"avg_ml_confidence={avg_conf:.3f} < floor={self.drift_confidence_floor}"
                )
                return f"DRIFT detected — {self._drift_reason}", "warning"

        # 2. Feedback rate spike
        fb_rate = sum(self._feedback_flags) / n
        if fb_rate > self.drift_feedback_rate:
            self._drift_detected = True
            self._drift_reason = (
                f"feedback_rate={fb_rate:.1%} > threshold={self.drift_feedback_rate:.1%}"
            )
            return f"DRIFT detected — {self._drift_reason}", "warning"

        # 3. Uncertain zone rate too high
        uncertain_rate = sum(1 for z in self._zones if z == "uncertain") / n
        if uncertain_rate > self.drift_uncertain_rate:
            self._drift_detected = True
            self._drift_reason = (
                f"uncertain_rate={uncertain_rate:.1%} > threshold={self.drift_uncertain_rate:.1%}"
            )
            return f"DRIFT detected — {self._drift_reason}", "warning"

        # All checks pass — clear drift flag
        was_drifted = self._drift_detected
        self._drift_detected = False
        self._drift_reason = None
        if was_drifted:
            return "drift cleared", "info"
        return None, None

    def clear_drift(self) -> None:
        """Manually clear drift flag (e.g. after a successful retrain)."""
        with self._lock:
            self._drift_detected = False
            self._drift_reason = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_drifted(self) -> bool:
        with self._lock:
            return self._drift_detected

    @property
    def drift_reason(self) -> Optional[str]:
        with self._lock:
            return self._drift_reason

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard(self) -> Dict:
        """Return a snapshot dict suitable for logging or a status endpoint."""
        with self._lock:
            n = len(self._confidences)
            if n == 0:
                return {"total_decisions": 0, "window_size": 0}

            # Source distribution
            source_counts: Dict[str, int] = {}
            for s in self._sources:
                source_counts[s] = source_counts.get(s, 0) + 1

            # Zone distribution (rolling window)
            zone_counts: Dict[str, int] = {}
            for z in self._zones:
                zone_counts[z] = zone_counts.get(z, 0) + 1

            ml_strong_rate    = zone_counts.get("ml_strong_correct", 0) / n
            ml_original_rate  = zone_counts.get("ml_strong_original", 0) / n
            uncertain_rate    = zone_counts.get("uncertain", 0) / n
            heuristic_rate    = sum(1 for s in self._sources if "ml" not in s) / n

            # Confidence stats (raw)
            ml_confs: List[float] = [
                c for c, s in zip(self._confidences, self._sources) if "ml" in s
            ]
            avg_confidence = sum(ml_confs) / len(ml_confs) if ml_confs else 0.0
            confidence_std = _std(ml_confs) if len(ml_confs) > 1 else 0.0

            # Calibrated confidence stats
            cal_confs: List[float] = [
                c for c, s in zip(self._calibrated_confidences, self._sources) if "ml" in s
            ]
            avg_calibrated_confidence = sum(cal_confs) / len(cal_confs) if cal_confs else 0.0

            correction_rate = (
                source_counts.get("phonetic_ml", 0) + source_counts.get("phonetic", 0)
            ) / n if n else 0.0

            return {
                # Rolling window stats
                "window_size":               n,
                "window_max":                self.window,
                "source_distribution":       source_counts,
                "correction_rate":           round(correction_rate, 3),
                # Confidence
                "avg_confidence":            round(avg_confidence, 4),
                "confidence_std":            round(confidence_std, 4),
                "avg_calibrated_confidence": round(avg_calibrated_confidence, 4),
                # Zone distribution
                "ml_strong_rate":            round(ml_strong_rate, 3),
                "ml_original_rate":          round(ml_original_rate, 3),
                "uncertain_rate":            round(uncertain_rate, 3),
                "heuristic_rate":            round(heuristic_rate, 3),
                # Feedback
                "feedback_rate":             round(sum(self._feedback_flags) / n, 3),
                # All-time counters
                "total_decisions":           self._total_decisions,
                "total_ml_decisions":        self._total_ml_decisions,
                "total_heuristic":           self._total_heuristic_decisions,
                "total_feedback":            self._total_feedback,
                "total_ml_strong_correct":   self._total_ml_strong_correct,
                "total_ml_strong_original":  self._total_ml_strong_original,
                "total_uncertain":           self._total_uncertain,
                # Drift
                "drift_detected":            self._drift_detected,
                "drift_reason":              self._drift_reason,
            }


def _std(values: List[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)
