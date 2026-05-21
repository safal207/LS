from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intent.operator_strategy import WhyStrategy


_RE_CHALLENGE = re.compile(r"почему\s+(?:бы\s+)?не\b|why\s+not|drawback|минус|проблем", re.I)
_RE_EXAMPLE = re.compile(r"расскажи|приведи\s+пример|tell\s+me\s+about|give\s+(?:an?\s+)?example", re.I)
_RE_INTERRUPT = re.compile(r"\bподожди\b|\bстоп\b|\bwait\b|\bactually\b", re.I)
_RE_THEORY = re.compile(r"^(?:что\s+такое|explain|define|definition|объясни\s+понятие)", re.I)


@dataclass
class CounterpartyProfile:
    """Live model of the counterparty built from observed questions."""

    pressure_level: float = 0.0
    prefers_reasoning: bool = False
    prefers_examples: bool = False
    prefers_theory: bool = False
    interrupt_count: int = 0

    _n: int = field(default=0, repr=False)
    _pressure_sum: float = field(default=0.0, repr=False)
    _reason_count: int = field(default=0, repr=False)
    _example_count: int = field(default=0, repr=False)
    _theory_count: int = field(default=0, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def observe(self, question: str, strategy: "WhyStrategy") -> None:
        with self._lock:
            self._observe_locked(question, strategy)

    def _observe_locked(self, question: str, strategy: "WhyStrategy") -> None:
        self._n += 1
        text = question or ""

        pressure_score = {"low": 0.2, "medium": 0.5, "high": 0.9}.get(strategy.pressure, 0.5)
        if _RE_CHALLENGE.search(text):
            pressure_score = max(pressure_score, 0.85)
        self._pressure_sum += pressure_score
        self.pressure_level = round(self._pressure_sum / self._n, 3)

        if strategy.answer_type in ("reasoning", "defense"):
            self._reason_count += 1
        if strategy.answer_type == "experiential" or _RE_EXAMPLE.search(text):
            self._example_count += 1
        if strategy.answer_type == "definition" or _RE_THEORY.search(text):
            self._theory_count += 1
        if _RE_INTERRUPT.search(text):
            self.interrupt_count += 1

        threshold = max(1, round(self._n * 0.4))
        self.prefers_reasoning = self._reason_count >= threshold
        self.prefers_examples = self._example_count >= threshold
        self.prefers_theory = self._theory_count >= threshold

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "pressure_level": self.pressure_level,
                "prefers_reasoning": self.prefers_reasoning,
                "prefers_examples": self.prefers_examples,
                "prefers_theory": self.prefers_theory,
                "interrupt_count": self.interrupt_count,
                "questions_seen": self._n,
            }
