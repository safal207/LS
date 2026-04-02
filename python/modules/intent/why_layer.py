# -*- coding: utf-8 -*-
"""WHY Layer — causal intent extraction: *why* was this asked?

Pipeline position::

    IntentLayer → WhyLayer → AgentLoop

While IntentLayer answers "what does the user want?", WhyLayer answers
"*why* are they asking this?", "what kind of answer is expected?", and
"what traps are hidden in this question?".

This is the difference between:

    intent  → definition of "index"
    why     → evaluating reasoning depth about indexes (tradeoffs expected)

Designed for interview-copilot and cognitive-agent contexts where understanding
the *evaluator's intent* is as important as understanding the surface question.

Goals
-----
evaluate_knowledge    — Checking if you know the basics.
                        → answer type: conceptual
evaluate_reasoning    — Checking if you understand *why*, not just *what*.
                        → answer type: tradeoff
challenge_decision    — Questioning a choice / pushing back.
                        → answer type: tradeoff + defense
check_experience      — Asking for real-world examples, past work.
                        → answer type: experiential
clarification         — Follow-up, asking to elaborate or confirm.
                        → answer type: conceptual

Answer types
------------
conceptual    — Explain the concept clearly with an example.
practical     — Show how it's done / used in practice.
tradeoff      — Discuss pros, cons, and alternatives.
experiential  — Describe a real situation you faced.

Pressure levels
---------------
low     — Warm-up, basic question, no trap expected.
medium  — Depth expected; shallow answer will be followed up.
high    — Challenging question; wrong answer may disqualify.

Usage::

    why = WhyLayer()
    result = why.analyze("почему вы используете индексы?")
    # WhyIntent(goal='evaluate_reasoning', pressure_level='medium',
    #           expected_answer_type='tradeoff', follow_up_expected=True,
    #           hints=['объясни не только что, но и почему',
    #                  'добавь trade-offs', 'упомяни альтернативы'],
    #           confidence=0.88)

    item["_why"] = result.to_dict()
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Goal / level constants
# ---------------------------------------------------------------------------

class Goal:
    EVALUATE_KNOWLEDGE   = "evaluate_knowledge"
    EVALUATE_REASONING   = "evaluate_reasoning"
    CHALLENGE_DECISION   = "challenge_decision"
    CHECK_EXPERIENCE     = "check_experience"
    CLARIFICATION        = "clarification"


class Pressure:
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class AnswerType:
    CONCEPTUAL   = "conceptual"
    PRACTICAL    = "practical"
    TRADEOFF     = "tradeoff"
    EXPERIENTIAL = "experiential"


# ---------------------------------------------------------------------------
# WhyIntent
# ---------------------------------------------------------------------------

@dataclass
class WhyIntent:
    """Causal intent: the *reason* behind a question.

    Attributes:
        goal:                  Why the question was asked (Goal constant).
        pressure_level:        Expected difficulty / depth required.
        expected_answer_type:  What kind of answer satisfies the evaluator.
        follow_up_expected:    True when a shallow answer will be challenged.
        hints:                 Actionable coaching tips for answering.
        confidence:            Rule-match confidence 0.0–1.0.
        raw_text:              Original text that was analyzed.
    """
    goal:                 str
    pressure_level:       str
    expected_answer_type: str
    follow_up_expected:   bool
    hints:                List[str] = field(default_factory=list)
    confidence:           float = 0.0
    raw_text:             str = ""

    def to_dict(self) -> dict:
        return {
            "goal":                 self.goal,
            "pressure_level":       self.pressure_level,
            "expected_answer_type": self.expected_answer_type,
            "follow_up_expected":   self.follow_up_expected,
            "hints":                self.hints,
            "confidence":           round(self.confidence, 4),
        }

    def __repr__(self) -> str:
        return (
            f"WhyIntent(goal={self.goal!r}, pressure={self.pressure_level!r}, "
            f"type={self.expected_answer_type!r}, conf={self.confidence:.2f})"
        )


# ---------------------------------------------------------------------------
# Rule bank
# ---------------------------------------------------------------------------
# Each rule: (pattern, goal, pressure, answer_type, follow_up, confidence, hints_key)
# Rules are evaluated in order; first match wins (most specific first).

_RuleEntry = Tuple[re.Pattern, str, str, str, bool, float, str]

_RULES: List[_RuleEntry] = [
    # ── Challenge / pushback (high pressure) ──────────────────────────────
    (
        re.compile(r"почему\s+(?:бы\s+)?не\s+(?:использовать|применять|взять)", re.I),
        Goal.CHALLENGE_DECISION, Pressure.HIGH, AnswerType.TRADEOFF, True, 0.92,
        "challenge_negative",
    ),
    (
        re.compile(r"why\s+(?:not|wouldn'?t|don'?t)\s+use", re.I),
        Goal.CHALLENGE_DECISION, Pressure.HIGH, AnswerType.TRADEOFF, True, 0.92,
        "challenge_negative",
    ),
    (
        re.compile(r"(?:какие|what)\s+(?:недостатки|минусы|проблемы|drawbacks?|downsides?)", re.I),
        Goal.CHALLENGE_DECISION, Pressure.HIGH, AnswerType.TRADEOFF, True, 0.90,
        "challenge_flaws",
    ),
    (
        re.compile(r"(?:что\s+бы\s+вы|how\s+would\s+you)\s+(?:улучшили?|improved?|changed?)", re.I),
        Goal.CHALLENGE_DECISION, Pressure.HIGH, AnswerType.TRADEOFF, True, 0.88,
        "challenge_improve",
    ),
    (
        re.compile(r"(?:когда|when)\s+(?:не\s+стоит|you\s+should(?:n'?t|_not)\s+use)", re.I),
        Goal.CHALLENGE_DECISION, Pressure.MEDIUM, AnswerType.TRADEOFF, True, 0.87,
        "challenge_antipattern",
    ),

    # ── Experience checks (medium–high) ────────────────────────────────────
    (
        re.compile(r"(?:расскажи|tell\s+me|describe)\s+(?:о\s+(?:своём?|своём?)|about\s+a)", re.I),
        Goal.CHECK_EXPERIENCE, Pressure.MEDIUM, AnswerType.EXPERIENTIAL, True, 0.90,
        "experience_story",
    ),
    (
        re.compile(r"(?:в\s+каких|in\s+what)\s+(?:случаях|ситуациях|scenarios?|cases?)", re.I),
        Goal.CHECK_EXPERIENCE, Pressure.MEDIUM, AnswerType.EXPERIENTIAL, True, 0.89,
        "experience_scenario",
    ),
    (
        re.compile(r"(?:как\s+(?:вы|ты|you)|have\s+you\s+ever)\s+(?:решали?|решили?|dealt?|handled?)", re.I),
        Goal.CHECK_EXPERIENCE, Pressure.MEDIUM, AnswerType.EXPERIENTIAL, True, 0.88,
        "experience_past",
    ),
    (
        re.compile(r"(?:приведи|give\s+(?:me\s+)?an?\s+example|покажи\s+пример)", re.I),
        Goal.CHECK_EXPERIENCE, Pressure.MEDIUM, AnswerType.PRACTICAL, True, 0.86,
        "experience_example",
    ),
    (
        re.compile(r"(?:с\s+какими|what)\s+(?:проблемами|challenges?|issues?)\s+(?:сталкивались?|you.ve?\s+faced?)", re.I),
        Goal.CHECK_EXPERIENCE, Pressure.HIGH, AnswerType.EXPERIENTIAL, True, 0.91,
        "experience_problems",
    ),

    # ── Reasoning / WHY (medium pressure) ─────────────────────────────────
    (
        re.compile(r"почему\s+(?!не\s)(.+)", re.I),
        Goal.EVALUATE_REASONING, Pressure.MEDIUM, AnswerType.TRADEOFF, True, 0.88,
        "reasoning_why",
    ),
    (
        re.compile(r"why\s+(?!not\s)(?:do|does|is|are|would|should)", re.I),
        Goal.EVALUATE_REASONING, Pressure.MEDIUM, AnswerType.TRADEOFF, True, 0.88,
        "reasoning_why",
    ),
    (
        re.compile(r"(?:зачем|для\s+чего|what\s+(?:is\s+the\s+)?(?:purpose|point|reason))", re.I),
        Goal.EVALUATE_REASONING, Pressure.MEDIUM, AnswerType.TRADEOFF, True, 0.87,
        "reasoning_purpose",
    ),
    (
        re.compile(r"(?:чем\s+отличается?|difference\s+between|compare\b|vs\.?\b)", re.I),
        Goal.EVALUATE_REASONING, Pressure.MEDIUM, AnswerType.TRADEOFF, True, 0.86,
        "reasoning_compare",
    ),
    (
        re.compile(r"(?:преимущества?|benefits?|advantages?)\s+(?:перед|over|of|от)", re.I),
        Goal.EVALUATE_REASONING, Pressure.MEDIUM, AnswerType.TRADEOFF, False, 0.85,
        "reasoning_benefits",
    ),

    # ── Practical / how-to (low–medium) ────────────────────────────────────
    (
        re.compile(r"(?:как\s+(?:правильно\s+)?(?:реализовать|implement|настроить|setup))", re.I),
        Goal.EVALUATE_KNOWLEDGE, Pressure.MEDIUM, AnswerType.PRACTICAL, False, 0.85,
        "practical_implement",
    ),
    (
        re.compile(r"(?:how\s+to\s+(?:implement|set\s+up|configure|use))", re.I),
        Goal.EVALUATE_KNOWLEDGE, Pressure.MEDIUM, AnswerType.PRACTICAL, False, 0.85,
        "practical_implement",
    ),

    # ── Clarification (low pressure) ──────────────────────────────────────
    (
        re.compile(r"(?:можешь?\s+уточнить|что\s+ты\s+имеешь?\s+в\s+виду|can\s+you\s+clarify|what\s+do\s+you\s+mean)", re.I),
        Goal.CLARIFICATION, Pressure.LOW, AnswerType.CONCEPTUAL, False, 0.93,
        "clarification",
    ),
    (
        re.compile(r"(?:поясни|расшифруй|elaborate|explain\s+more)", re.I),
        Goal.CLARIFICATION, Pressure.LOW, AnswerType.CONCEPTUAL, False, 0.88,
        "clarification",
    ),

    # ── Knowledge check (low pressure, broadest — last) ────────────────────
    (
        re.compile(r"(?:что\s+такое|что\s+это|what\s+is\b|explain\b|расскажи\s+(?:про|о))", re.I),
        Goal.EVALUATE_KNOWLEDGE, Pressure.LOW, AnswerType.CONCEPTUAL, False, 0.82,
        "knowledge_basic",
    ),
    (
        re.compile(r"(?:как\s+работает?|how\s+(?:does|do)\s+\w+\s+work)", re.I),
        Goal.EVALUATE_KNOWLEDGE, Pressure.LOW, AnswerType.CONCEPTUAL, True, 0.83,
        "knowledge_mechanism",
    ),
]


# ---------------------------------------------------------------------------
# Hint bank (per hints_key, optionally entity-interpolated)
# ---------------------------------------------------------------------------

_HINTS: Dict[str, List[str]] = {
    "challenge_negative": [
        "Признай ограничения подхода честно",
        "Добавь trade-offs и когда это всё же оправдано",
        "Предложи альтернативы с объяснением почему не выбрал их",
    ],
    "challenge_flaws": [
        "Назови 2–3 конкретных недостатка",
        "Объясни в каких сценариях они критичны",
        "Упомяни как их митигировать",
    ],
    "challenge_improve": [
        "Критикуй конкретно, с примерами",
        "Предложи улучшение и объясни его стоимость",
        "Покажи что понимаешь компромиссы",
    ],
    "challenge_antipattern": [
        "Назови anti-pattern сценарии",
        "Объясни почему это важно знать",
        "Свяжи с реальным опытом если есть",
    ],
    "experience_story": [
        "Используй STAR-метод: Situation, Task, Action, Result",
        "Дай конкретные цифры/метрики если возможно",
        "Заверши выводом — что ты вынес из этого",
    ],
    "experience_scenario": [
        "Дай 2–3 конкретных сценария, не абстрактных",
        "Для каждого — почему именно этот подход",
        "Упомяни один сценарий где это НЕ подходит",
    ],
    "experience_past": [
        "Расскажи конкретную ситуацию (не гипотетическую)",
        "Фокус на твоих действиях и решениях",
        "Результат — что изменилось после твоего решения",
    ],
    "experience_example": [
        "Приведи реальный пример из практики",
        "Объясни контекст за 1–2 предложения",
        "Добавь почему ты выбрал именно это решение",
    ],
    "experience_problems": [
        "Назови конкретную проблему и её причину",
        "Опиши как ты её диагностировал",
        "Расскажи о решении и уроках",
    ],
    "reasoning_why": [
        "Объясни не только ЧТО, но и ПОЧЕМУ",
        "Добавь trade-offs — что теряешь, что выигрываешь",
        "Упомяни альтернативы и почему ты не выбрал их",
    ],
    "reasoning_purpose": [
        "Объясни цель/проблему которую это решает",
        "Покажи что будет без этого",
        "Свяжи с реальным use-case",
    ],
    "reasoning_compare": [
        "Структурируй ответ: X vs Y по конкретным критериям",
        "Не просто перечисляй — объясни когда что предпочесть",
        "Заверши рекомендацией с условием",
    ],
    "reasoning_benefits": [
        "Назови 3+ конкретных преимущества",
        "Для каждого — в каком сценарии оно важно",
        "Добавь один честный недостаток — это показывает зрелость",
    ],
    "practical_implement": [
        "Опиши шаги реализации кратко и структурно",
        "Упомяни edge-cases и ошибки которые легко допустить",
        "Если знаешь — назови best practices",
    ],
    "clarification": [
        "Переформулируй вопрос своими словами для подтверждения",
        "Ответь конкретно на уточнённый вопрос",
    ],
    "knowledge_basic": [
        "Дай чёткое определение за 1–2 предложения",
        "Приведи конкретный пример применения",
        "Упомяни ключевые характеристики",
    ],
    "knowledge_mechanism": [
        "Объясни механизм шаг за шагом",
        "Используй аналогию если концепт сложный",
        "Свяжи с практическим следствием этого механизма",
    ],
}


# ---------------------------------------------------------------------------
# WhyLayer
# ---------------------------------------------------------------------------

class WhyLayer:
    """Causal intent extraction: *why* was this question asked?

    Rule-based engine with 15 patterns covering the main interview question
    archetypes.  Optionally enriches hints with the entity from IntentResult.

    Args:
        min_confidence: Results below this are typed as EVALUATE_KNOWLEDGE
                        with LOW pressure (safe fallback).
    """

    def __init__(self, min_confidence: float = 0.0) -> None:
        self.min_confidence = min_confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, text: str, intent: Optional[dict] = None) -> WhyIntent:
        """Analyze *text* and return a :class:`WhyIntent`.

        Args:
            text:   Resolved utterance (after SmartEar correction).
            intent: Optional ``_intent`` dict from IntentLayer for richer
                    hint generation (entity, type, etc.).
        """
        if not text or not text.strip():
            return self._fallback(text)

        text = text.strip()
        result = self._match_rules(text)

        # Enrich hints with entity from IntentLayer
        if intent:
            result = self._enrich_hints(result, intent)

        return result

    def process_item(self, item: dict) -> dict:
        """Enrich a SmartEar item dict in-place with ``_why`` field.

        Reads ``item["text"]`` and ``item.get("_intent")``, runs causal
        analysis, and sets ``item["_why"]`` to the serialised WhyIntent.

        Returns the same item (mutated).
        """
        text = item.get("text", "")
        intent = item.get("_intent")
        result = self.analyze(text, intent=intent)
        item["_why"] = result.to_dict()
        logger.debug("WhyLayer: %r → %s", text[:60], result)
        return item

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _match_rules(self, text: str) -> WhyIntent:
        for pattern, goal, pressure, answer_type, follow_up, conf, hints_key in _RULES:
            if pattern.search(text) is None:
                continue
            if conf < self.min_confidence:
                continue
            hints = list(_HINTS.get(hints_key, []))
            return WhyIntent(
                goal=goal,
                pressure_level=pressure,
                expected_answer_type=answer_type,
                follow_up_expected=follow_up,
                hints=hints,
                confidence=round(conf, 4),
                raw_text=text,
            )
        return self._fallback(text)

    def _fallback(self, text: str) -> WhyIntent:
        return WhyIntent(
            goal=Goal.EVALUATE_KNOWLEDGE,
            pressure_level=Pressure.LOW,
            expected_answer_type=AnswerType.CONCEPTUAL,
            follow_up_expected=False,
            hints=list(_HINTS["knowledge_basic"]),
            confidence=0.0,
            raw_text=text,
        )

    def _enrich_hints(self, result: WhyIntent, intent: dict) -> WhyIntent:
        """Personalize hints using the entity from IntentLayer."""
        entity = intent.get("entity", "").strip()
        if not entity:
            return result

        enriched = []
        for hint in result.hints:
            # Replace generic placeholders with the actual entity
            hint = re.sub(r"\bX\b", entity, hint)
            enriched.append(hint)

        # Append entity-specific tip for high pressure challenges
        if (
            result.pressure_level == Pressure.HIGH
            and result.goal == Goal.CHALLENGE_DECISION
            and entity
        ):
            enriched.append(f"Будь готов защищать {entity} с цифрами или реальным примером")

        result.hints = enriched
        return result
