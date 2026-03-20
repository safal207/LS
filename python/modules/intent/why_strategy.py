"""WHY Strategy — battle-ready answer strategy from question type.

Lightweight, zero-dependency module for real-time interview coaching.
No ML, no embeddings — just fast pattern matching → actionable hints.

Unlike the research-oriented ``why_layer.py``, this module is optimised for
*latency* and *directness*: the result must be usable in < 1 ms and the hints
must be usable *verbatim* as a one-line screen overlay.

Usage::

    strategy = analyze_why_and_strategy("почему вы используете индексы?")
    # WhyStrategy(goal='evaluate_reasoning', pressure='high',
    #   answer_type='reasoning',
    #   hints=['скажи причину', 'добавь плюсы и минусы', 'упомяни альтернативу'],
    #   confidence=0.9)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from intent.interviewer_profile import InterviewerProfile


# Micro-trigger: one line per answer_type, read in 0.5 sec under stress.
# This is the only thing that matters when the brain freezes.
_MICRO_TRIGGERS: dict[str, str] = {
    "reasoning":    "объясни причину + добавь кейс",
    "defense":      "защити решение + покажи trade-offs",
    "list":         "просто перечисли",
    "definition":   "дай определение + пример",
    "practical":    "опиши шаги + edge-case",
    "experiential": "STAR: ситуация → что сделал → результат",
    "short":        "ответь кратко",
}


@dataclass
class WhyStrategy:
    """Actionable answer strategy for a single question.

    Attributes:
        goal:          Why this question is being asked.
        pressure:      low | medium | high — stakes of a shallow answer.
        answer_type:   reasoning | defense | list | definition | short
        hints:         Ordered coaching tips (first = most important).
        confidence:    Pattern-match confidence 0.0–1.0.
        micro_trigger: Single-line directive for zero-latency recall under stress.
    """
    goal:          str
    pressure:      str
    answer_type:   str
    hints:         List[str] = field(default_factory=list)
    confidence:    float = 0.5
    micro_trigger: str = ""

    def __post_init__(self) -> None:
        if not self.micro_trigger:
            self.micro_trigger = _MICRO_TRIGGERS.get(self.answer_type, "ответь кратко")

    def to_dict(self) -> dict:
        return {
            "goal":          self.goal,
            "pressure":      self.pressure,
            "answer_type":   self.answer_type,
            "micro_trigger": self.micro_trigger,
            "hints":         self.hints,
            "confidence":    round(self.confidence, 4),
        }

    def apply_interviewer_bias(self, profile: "InterviewerProfile") -> None:
        """Hard-bind answer mode based on what this interviewer cares about.

        Called once per question, after InterviewerProfile.observe().
        Mutates self in-place — no new object needed.

        Rules (in priority order):
          1. goal == "check_experience"  → force experiential + anchor
          2. goal == "challenge" + high pressure interviewer → force defense
          3. interviewer prefers_examples → bump to experiential if not already
          4. interviewer prefers_reasoning → ensure reasoning hints present
        """
        # Rule 1 — experience question: always force STAR + anchor directive
        if self.goal in ("check_experience", "evaluate_experience"):
            self.answer_type = "experiential"
            self.micro_trigger = "STAR: ситуация → что сделал → результат"
            if "дай конкретные цифры/метрики если есть" not in self.hints:
                self.hints.insert(0, "ОБЯЗАТЕЛЬНО приведи свой кейс с цифрами")

        # Rule 2 — challenge under a high-pressure interviewer
        elif self.goal == "challenge" and profile.pressure_level >= 0.7:
            self.answer_type = "defense"
            self.pressure = "high"
            self.micro_trigger = "защити решение + покажи trade-offs"
            if "покажи trade-offs" not in " ".join(self.hints):
                self.hints.insert(0, "покажи trade-offs явно")

        # Rule 3 — interviewer consistently wants real examples
        elif profile.prefers_examples and self.answer_type == "reasoning":
            self.answer_type = "experiential"
            self.micro_trigger = "STAR: ситуация → что сделал → результат"
            self.hints.append("добавь свой кейс в конце")

        # Rule 4 — interviewer likes reasoning: strengthen reasoning hints
        elif profile.prefers_reasoning and self.answer_type == "definition":
            self.answer_type = "reasoning"
            self.micro_trigger = _MICRO_TRIGGERS["reasoning"]
            self.hints.append("объясни своими словами почему")

    def format_prompt_block(self) -> str:
        """Return a compact block ready for injection into a system prompt.

        The micro-trigger is the first line — it must be visible at a glance.
        """
        hints_text = "\n".join(f"- {h}" for h in self.hints)
        return (
            f"🧠 Сейчас: {self.micro_trigger}\n\n"
            f"Стратегия: {self.answer_type}  |  Давление: {self.pressure}\n"
            f"Подсказки:\n{hints_text}"
        )


# ---------------------------------------------------------------------------
# Pattern rules: (compiled_pattern, goal, pressure, answer_type, confidence, hints)
# ---------------------------------------------------------------------------

_RuleT = Tuple[re.Pattern, str, str, str, float, List[str]]

_RULES: List[_RuleT] = [
    # WHY NOT — highest pressure: someone is challenging your decision
    (
        re.compile(r"почему\s+(?:бы\s+)?не\b|why\s+(?:not|wouldn'?t)", re.I),
        "challenge", "high", "defense", 0.95,
        [
            "объясни выбор",
            "сравни с альтернативой",
            "покажи trade-offs",
        ],
    ),
    # WHY — reasoning depth expected
    (
        re.compile(r"^почему\b|^зачем\b|^why\b|^what(?:'s| is) the reason\b", re.I),
        "evaluate_reasoning", "high", "reasoning", 0.9,
        [
            "скажи причину",
            "добавь плюсы и минусы",
            "упомяни альтернативу",
        ],
    ),
    # FLAWS / CONS — they want you to be critical
    (
        re.compile(r"(?:какие|what)\s+(?:минусы|недостатки|проблемы|drawbacks?|downsides?|cons\b)", re.I),
        "challenge", "high", "defense", 0.92,
        [
            "назови 2–3 конкретных минуса",
            "скажи в каком сценарии это критично",
            "предложи как митигировать",
        ],
    ),
    # DIFFERENCE / COMPARE — structured comparison needed
    (
        re.compile(r"чем\s+отличается?|разница|(?:compare|difference\s+between|vs\.?\s)", re.I),
        "compare", "medium", "reasoning", 0.88,
        [
            "назови 2–3 критерия сравнения",
            "не просто список — скажи когда что лучше",
            "дай итоговую рекомендацию",
        ],
    ),
    # ENUMERATE / LIST — just give the list, don't dig deep
    (
        re.compile(r"перечисли|назови\s+(?:все\s+)?(?:типы|виды|способы)|list\s+(?:all\s+)?(?:types?|ways?)", re.I),
        "check_basics", "medium", "list", 0.85,
        [
            "дай список",
            "не углубляйся",
            "будь чётким",
        ],
    ),
    # WHEN / WHICH CASES — experience / scenario check
    (
        re.compile(r"в\s+каких\s+(?:случаях|ситуациях)|когда\s+(?:стоит|лучше|нужно)|when\s+(?:should|would\s+you)", re.I),
        "check_experience", "medium", "reasoning", 0.87,
        [
            "дай 2–3 конкретных сценария",
            "для каждого — почему именно так",
            "добавь один анти-паттерн",
        ],
    ),
    # TELL ME ABOUT / DESCRIBE YOUR EXPERIENCE
    (
        re.compile(r"расскажи\s+(?:о\s+)?(?:своём?|своём?|своем)|tell\s+me\s+about\s+(?:a\s+time|your)", re.I),
        "check_experience", "medium", "experiential", 0.88,
        [
            "STAR: ситуация → задача → действие → результат",
            "дай конкретные цифры/метрики если есть",
            "заверши выводом — что вынес",
        ],
    ),
    # HOW — practical implementation
    (
        re.compile(r"^как\s+(?:правильно\s+)?(?:реализовать|настроить|сделать|implement|setup|configure)", re.I),
        "evaluate_knowledge", "medium", "practical", 0.84,
        [
            "опиши шаги кратко",
            "упомяни edge-case",
            "назови best practice",
        ],
    ),
    # WHAT IS — definition
    (
        re.compile(r"^(?:что\s+такое|что\s+(?:это|есть)|what\s+is\b|explain\b)", re.I),
        "evaluate_knowledge", "low", "definition", 0.82,
        [
            "дай чёткое определение",
            "приведи пример",
            "назови ключевые свойства",
        ],
    ),
]

_DEFAULT = WhyStrategy(
    goal="general",
    pressure="low",
    answer_type="short",
    hints=["ответь кратко", "будь понятным"],
    confidence=0.5,
)


def analyze_why_and_strategy(text: str) -> WhyStrategy:
    """Extract answer strategy from *text* using fast rule matching.

    Returns a :class:`WhyStrategy`.  Never raises.
    """
    if not text or not text.strip():
        return _DEFAULT

    t = text.strip()
    for pattern, goal, pressure, answer_type, conf, hints in _RULES:
        if pattern.search(t):
            return WhyStrategy(
                goal=goal,
                pressure=pressure,
                answer_type=answer_type,
                hints=list(hints),
                confidence=conf,
            )

    return WhyStrategy(
        goal=_DEFAULT.goal,
        pressure=_DEFAULT.pressure,
        answer_type=_DEFAULT.answer_type,
        hints=list(_DEFAULT.hints),
        confidence=_DEFAULT.confidence,
    )
