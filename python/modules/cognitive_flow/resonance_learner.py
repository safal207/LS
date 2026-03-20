"""ResonanceLearner — continuous learning from completed cognitive cycles.

After each cycle is completed (LLM responded, optional user feedback added),
the learner:

1. Reads the ``resonance_score`` and ``user_feedback`` from the cycle record.
2. Identifies which pipeline rules fired (``copilot.active_rules``).
3. Updates a per-rule weight table: rules that correlate with high resonance
   get a positive bias; rules that correlate with low resonance get penalised.
4. Persists the weight table to a JSON file so biases survive restarts.

The weights are consumed by ``WhyStrategy.apply_interviewer_bias`` and
``EmpathyNegotiationLayer._build`` through a shared ``get_bias(rule)`` call.
Integration is opt-in — callers may ignore the weights; the pipeline works
identically without them.

Weight update rule
------------------
    delta = (resonance_score − 0.5) × LEARNING_RATE × rule_contribution

    where rule_contribution = 1.0 / len(active_rules)   (equal credit)

    LEARNING_RATE = 0.05  (conservative, avoids rapid drift)

    Weights are clamped to [−MAX_BIAS, +MAX_BIAS] = [−0.40, +0.40]

Negative user feedback multiplies the delta by −FEEDBACK_PENALTY so a single
explicit "wrong" signal can undo a string of implicit positive updates.

Thread safety
-------------
All public methods are guarded by ``threading.Lock``.

Usage::

    learner = ResonanceLearner(path="logs/resonance_weights.json")

    # After each cycle completes:
    learner.learn(cycle_record)   # cycle_record from CognitiveCycleLogger

    # In rule engine (optional integration):
    bias = learner.get_bias("high_pressure_warm")  # e.g. +0.07

    # Persist / reload:
    learner.save()
    learner.load()
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_LEARNING_RATE:   float = 0.05
_MAX_BIAS:        float = 0.40
_FEEDBACK_PENALTY: float = 3.0   # explicit negative feedback multiplier
_MIN_RESONANCE_GOOD: float = 0.70
_MAX_RESONANCE_BAD:  float = 0.45


class ResonanceLearner:
    """Continuous learner that adapts rule biases from completed cycle records.

    Args:
        path:      JSON file for weight persistence.  Empty string → no I/O.
        auto_save: If True, save() is called automatically after every learn().
    """

    def __init__(self, path: str = "", auto_save: bool = True) -> None:
        self._path     = path
        self._auto_save = auto_save
        self._lock     = threading.Lock()
        self._weights: Dict[str, float] = {}  # rule_name → bias
        self._cycle_count = 0
        if path:
            self._load_locked()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def learn(self, cycle: dict) -> None:
        """Update weights from a completed cycle record.

        Args:
            cycle: A dict as produced by :class:`CognitiveCycleLogger` —
                   must contain ``resonance_score`` and optionally
                   ``copilot.active_rules`` and ``user_feedback``.
        """
        resonance = float(cycle.get("resonance_score") or 0.5)
        copilot   = cycle.get("copilot") or {}
        rules     = list(copilot.get("active_rules") or [])
        feedback  = cycle.get("user_feedback")

        if not rules:
            return  # nothing to update

        # Explicit negative feedback reverses the learning signal
        negative_fb = isinstance(feedback, str) and bool(feedback.strip())
        delta_sign  = -_FEEDBACK_PENALTY if negative_fb else 1.0

        # Equal credit attribution across all active rules
        contribution = 1.0 / len(rules)
        delta_per_rule = (resonance - 0.5) * _LEARNING_RATE * contribution * delta_sign

        with self._lock:
            for rule in rules:
                current = self._weights.get(rule, 0.0)
                updated = max(-_MAX_BIAS, min(_MAX_BIAS, current + delta_per_rule))
                self._weights[rule] = round(updated, 4)
            self._cycle_count += 1

        logger.debug(
            "ResonanceLearner: learned from cycle (resonance=%.3f rules=%s Δ=%.4f neg_fb=%s)",
            resonance, rules, delta_per_rule, negative_fb,
        )

        if self._auto_save and self._path:
            self.save()

    def get_bias(self, rule: str) -> float:
        """Return the current learned bias for *rule* (0.0 if unknown)."""
        with self._lock:
            return self._weights.get(rule, 0.0)

    def top_rules(self, n: int = 10) -> list[tuple[str, float]]:
        """Return top-*n* rules sorted by absolute weight (for inspection)."""
        with self._lock:
            ranked = sorted(
                self._weights.items(), key=lambda kv: abs(kv[1]), reverse=True
            )
            return ranked[:n]

    def save(self) -> None:
        """Persist weights to the configured JSON file."""
        if not self._path:
            return
        with self._lock:
            data = {
                "version":     1,
                "cycle_count": self._cycle_count,
                "weights":     dict(self._weights),
            }
        try:
            dir_path = os.path.dirname(os.path.abspath(self._path))
            os.makedirs(dir_path, exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)   # atomic on POSIX
            logger.debug("ResonanceLearner: saved %d weights → %s", len(data["weights"]), self._path)
        except Exception as exc:
            logger.warning("ResonanceLearner: save failed: %s", exc)

    def load(self) -> None:
        """Reload weights from disk (replaces current in-memory state)."""
        with self._lock:
            self._load_locked()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_locked(self) -> None:
        """Load weights from disk — caller must NOT hold _lock."""
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = json.load(fh)
            self._weights     = {str(k): float(v) for k, v in data.get("weights", {}).items()}
            self._cycle_count = int(data.get("cycle_count", 0))
            logger.info(
                "ResonanceLearner: loaded %d weights (%d cycles) from %s",
                len(self._weights), self._cycle_count, self._path,
            )
        except Exception as exc:
            logger.warning("ResonanceLearner: load failed: %s", exc)

    @property
    def cycle_count(self) -> int:
        with self._lock:
            return self._cycle_count

    @property
    def weight_count(self) -> int:
        with self._lock:
            return len(self._weights)
