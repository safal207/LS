"""SmartEar online metrics — rolling window tracker + drift detection.

Tracks every SelectionStage decision in memory.  Provides a ``get_dashboard()``
snapshot for monitoring and detects model drift automatically.

Drift triggers:
* Rolling average model confidence drops below ``drift_confidence_floor``.
* Correction-to-original ratio shifts significantly vs baseline.
* User feedback rate spikes (humans keep correcting the model).

When drift is detected, ``is_drifted`` becomes ``True`` and the decision model
is flagged for fallback until a retrain completes.

Usage::

    from smart_ear.metrics import SmartEarMetrics

    metrics = SmartEarMetrics(window=200, drift_confidence_floor=0.55)

    # In SelectionStage:
    metrics.record(source="phonetic_ml", model_confidence=0.82, was_corrected=True)

    # Anywhere for monitoring:
    print(metrics.get_dashboard())

    # In SelectionStage before deciding:
    if metrics.is_drifted:
        # force heuristic fallback
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Deque, Dict, Optional

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
    """

    def __init__(
        self,
        window: int = 200,
        drift_confidence_floor: float = 0.45,
        drift_feedback_rate: float = 0.30,
    ) -> None:
        self.window = window
        self.drift_confidence_floor = drift_confidence_floor
        self.drift_feedback_rate = drift_feedback_rate

        # Rolling deques — each element is a float or bool
        self._confidences: Deque[float] = collections.deque(maxlen=window)
        self._sources: Deque[str] = collections.deque(maxlen=window)
        self._feedback_flags: Deque[bool] = collections.deque(maxlen=window)

        # Counters (all-time, not windowed)
        self._total_decisions = 0
        self._total_ml_decisions = 0
        self._total_heuristic_decisions = 0
        self._total_feedback = 0

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
        is_feedback: bool = False,
    ) -> None:
        """Record one SelectionStage decision.

        Parameters
        ----------
        source:
            ``"original"``, ``"phonetic"``, ``"phonetic_ml"``, etc.
        model_confidence:
            Probability returned by the model (0 if heuristic used).
        is_feedback:
            True when this decision was triggered by ``user_feedback()``,
            meaning the human disagreed with the system's prior choice.
        """
        log_msg: Optional[str] = None
        log_level = "warning"

        with self._lock:
            self._confidences.append(model_confidence)
            self._sources.append(source)
            self._feedback_flags.append(is_feedback)

            self._total_decisions += 1
            if "ml" in source:
                self._total_ml_decisions += 1
            else:
                self._total_heuristic_decisions += 1
            if is_feedback:
                self._total_feedback += 1

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

        ml_confs = [c for c, s in zip(self._confidences, self._sources) if "ml" in s]
        if len(ml_confs) >= 10:
            avg_conf = sum(ml_confs) / len(ml_confs)
            if avg_conf < self.drift_confidence_floor:
                self._drift_detected = True
                self._drift_reason = (
                    f"avg_ml_confidence={avg_conf:.3f} < floor={self.drift_confidence_floor}"
                )
                return f"DRIFT detected — {self._drift_reason}", "warning"

        fb_rate = sum(self._feedback_flags) / n
        if fb_rate > self.drift_feedback_rate:
            self._drift_detected = True
            self._drift_reason = (
                f"feedback_rate={fb_rate:.1%} > threshold={self.drift_feedback_rate:.1%}"
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

            source_counts: Dict[str, int] = {}
            for s in self._sources:
                source_counts[s] = source_counts.get(s, 0) + 1

            ml_confs = [c for c, s in zip(self._confidences, self._sources) if "ml" in s]
            avg_conf = sum(ml_confs) / len(ml_confs) if ml_confs else 0.0

            correction_rate = source_counts.get("phonetic_ml", 0) + source_counts.get("phonetic", 0)
            correction_rate = correction_rate / n if n else 0.0

            return {
                # Rolling window stats
                "window_size":          n,
                "window_max":           self.window,
                "source_distribution":  source_counts,
                "correction_rate":      round(correction_rate, 3),
                "avg_ml_confidence":    round(avg_conf, 4),
                "feedback_rate":        round(sum(self._feedback_flags) / n, 3),
                # All-time counters
                "total_decisions":      self._total_decisions,
                "total_ml_decisions":   self._total_ml_decisions,
                "total_heuristic":      self._total_heuristic_decisions,
                "total_feedback":       self._total_feedback,
                # Drift
                "drift_detected":       self._drift_detected,
                "drift_reason":         self._drift_reason,
            }
