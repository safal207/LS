# -*- coding: utf-8 -*-
"""InterviewerProfile — historical real-time model of the counterparty built from their questions.

Each question is observed and the profile updates automatically.
The profile is then used by WhyStrategy.apply_interviewer_bias() to
hard-bind the answer mode before the prompt is generated.

Design goals:
- Zero dependencies, < 0.5 ms per observation
- Stateless from the outside: just call observe() each turn, read attrs anytime
- Simple enough to understand in 30 seconds during a live operator workflow

Usage::

    profile = InterviewerProfile()  # new code should prefer OperatorProfile

    # Each time a new question arrives:
    profile.observe("почему не использовали Redis?", strategy)
    profile.observe("расскажи о своём опыте с очередями", strategy)

    # Read state at any time:
    profile.prefers_examples   # True  — questions keep asking for experience
    profile.pressure_level     # 0.75  — challenge/defense questions dominate
    profile.to_dict()          # → serialisable summary for logging / injection
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intent.operator_strategy import WhyStrategy


# ---------------------------------------------------------------------------
# Cheap signal detectors (no imports needed)
# ---------------------------------------------------------------------------

_RE_CHALLENGE = re.compile(
    r"почему\s+(?:бы\s+)?не\b|why\s+not|drawback|минус|проблем", re.I
)
_RE_EXAMPLE = re.compile(
    r"расскажи|приведи\s+пример|tell\s+me\s+about|give\s+(?:an?\s+)?example", re.I
)
_RE_INTERRUPT = re.compile(r"\bподожди\b|\bстоп\b|\bwait\b|\bactually\b", re.I)
_RE_THEORY = re.compile(
    r"^(?:что\s+такое|explain|define|definition|объясни\s+понятие)", re.I
)


@dataclass
class InterviewerProfile:
    """Historical live model of the counterparty built from observed questions.

    New code should prefer ``OperatorProfile`` from ``intent.operator_profile``.

    Attributes:
        pressure_level:    0.0–1.0. High = counterparty applies challenge/pressure.
        prefers_reasoning: True when the counterparty keeps asking WHY/reasoning.
        prefers_examples:  True when the counterparty keeps asking for real cases.
        prefers_theory:    True when the counterparty prefers definitions/concepts.
        interrupt_count:   How many times the counterparty interrupted/redirected.
        _n:                Total questions observed (internal, for averaging).
        _pressure_sum:     Cumulative pressure score (internal).
    """
    pressure_level:    float = 0.0
    prefers_reasoning: bool  = False
    prefers_examples:  bool  = False
    prefers_theory:    bool  = False
    interrupt_count:   int   = 0

    # internal counters
    _n:            int   = field(default=0, repr=False)
    _pressure_sum: float = field(default=0.0, repr=False)
    _reason_count: int   = field(default=0, repr=False)
    _example_count: int  = field(default=0, repr=False)
    _theory_count: int   = field(default=0, repr=False)
    # lock is not part of the dataclass repr/eq/hash
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def observe(self, question: str, strategy: "WhyStrategy") -> None:
        """Update the profile from a single (question, strategy) pair.

        Call this once per question, before apply_interviewer_bias().
        Thread-safe: multiple pipeline threads may call observe() concurrently.
        """
        with self._lock:
            self._observe_locked(question, strategy)

    def _observe_locked(self, question: str, strategy: "WhyStrategy") -> None:
        """Inner implementation — must be called with self._lock held."""
        self._n += 1
        text = question or ""

        # --- pressure signal ---
        pressure_score = {"low": 0.2, "medium": 0.5, "high": 0.9}.get(
            strategy.pressure, 0.5
        )
        if _RE_CHALLENGE.search(text):
            pressure_score = max(pressure_score, 0.85)
        self._pressure_sum += pressure_score
        self.pressure_level = round(self._pressure_sum / self._n, 3)

        # --- style signals ---
        if strategy.answer_type in ("reasoning", "defense"):
            self._reason_count += 1
        if strategy.answer_type == "experiential" or _RE_EXAMPLE.search(text):
            self._example_count += 1
        if strategy.answer_type == "definition" or _RE_THEORY.search(text):
            self._theory_count += 1
        if _RE_INTERRUPT.search(text):
            self.interrupt_count += 1

        # update boolean flags: flip to True once ≥ 40 % of questions match
        threshold = max(1, round(self._n * 0.4))
        self.prefers_reasoning = self._reason_count >= threshold
        self.prefers_examples  = self._example_count >= threshold
        self.prefers_theory    = self._theory_count >= threshold

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "pressure_level":    self.pressure_level,
                "prefers_reasoning": self.prefers_reasoning,
                "prefers_examples":  self.prefers_examples,
                "prefers_theory":    self.prefers_theory,
                "interrupt_count":   self.interrupt_count,
                "questions_seen":    self._n,
            }
