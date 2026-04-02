# -*- coding: utf-8 -*-
"""EmpathyNegotiationLayer — Stage 7 of the SmartEar cognitive pipeline.

Adds empathic and negotiation-aware hints to the LLM prompt, based on:
  - InterviewerProfile (pressure, style preferences built from prior questions)
  - WHY Strategy (goal, answer_type, pressure level)
  - Anchor context (candidate's real experience)

Design goals
------------
* Zero hard dependencies — all imports are optional with graceful fallback.
* < 0.5 ms per call — pure rule matching, no ML, no I/O.
* Thread-safe — stateless output; only the shared InterviewerProfile is mutated
  and that happens in WhyStrategyStage before this layer runs.
* The LLM sees ONE extra block appended to the system prompt:

    💬 Тон: снизь давление — короткие фразы + подтверждение
    Подсказки:
    - Используй мягкий тон (давление 78%)
    - Подтверди понимание перед ответом: "Да, понимаю..."
    - Перефразируй сложное простыми словами
    - Добавь паузу: "хороший вопрос..."

Usage::

    layer = EmpathyNegotiationLayer()
    item = layer.process(item)          # item["_empathy_hints"] populated
    # → EmpathyResult serialisable via to_dict()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Tone categories and their LLM-facing labels
# ---------------------------------------------------------------------------

class _Tone:
    CALM      = "calm"       # steady, low pressure
    WARM      = "warm"       # empathetic, connecting
    ASSERTIVE = "assertive"  # confident, direct
    GROUNDED  = "grounded"   # experiential, concrete
    BRIEF     = "brief"      # short, interruptible


# Higher number = higher priority.  A rule can only RAISE the tone level,
# never lower it (BRIEF beats GROUNDED beats ASSERTIVE beats WARM beats CALM).
_TONE_PRIORITY: dict[str, int] = {
    _Tone.CALM:      0,
    _Tone.WARM:      1,
    _Tone.GROUNDED:  2,
    _Tone.ASSERTIVE: 3,
    _Tone.BRIEF:     4,
}

# Tone → first-line trigger visible in < 0.3 s
_TONE_TRIGGER: dict[str, str] = {
    _Tone.CALM:      "говори спокойно — короткие фразы",
    _Tone.WARM:      "подтверди понимание → затем ответь",
    _Tone.ASSERTIVE: "отвечай уверенно — факт + причина",
    _Tone.GROUNDED:  "говори через свой кейс — конкретно",
    _Tone.BRIEF:     "отвечай кратко — 2–3 предложения",
}

# Negotiation phrases that reduce perceived pressure
_SOFTENERS: dict[str, str] = {
    "opening":      "Да, понимаю — ...",
    "redirect":     "Хороший вопрос, давай разберём...",
    "bridge":       "Из своего опыта могу сказать...",
    "pause_phrase": "Дай подумаю секунду...",
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class EmpathyResult:
    """Output of EmpathyNegotiationLayer for one question.

    Attributes:
        tone:             Recommended tone category.
        tone_trigger:     One-line directive (shown first in prompt).
        hints:            Ordered list of coaching hints for the LLM.
        negotiation_move: Optional negotiation-softener phrase to open with.
        pressure_score:   0.0–1.0 — synthesised pressure this question.
        active_rules:     Which rule names fired (for logging/debugging).
    """
    tone:             str
    tone_trigger:     str
    hints:            List[str]          = field(default_factory=list)
    negotiation_move: Optional[str]      = None
    pressure_score:   float              = 0.0
    active_rules:     List[str]          = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tone":             self.tone,
            "tone_trigger":     self.tone_trigger,
            "hints":            self.hints,
            "negotiation_move": self.negotiation_move,
            "pressure_score":   round(self.pressure_score, 3),
            "active_rules":     self.active_rules,
        }

    def format_prompt_block(self) -> str:
        """Compact block for LLM system-prompt injection."""
        lines = "\n".join(f"- {h}" for h in self.hints)
        block = f"💬 Тон: {self.tone_trigger}\nПодсказки:\n{lines}"
        if self.negotiation_move:
            block += f'\nОткрой с: "{self.negotiation_move}"'
        return block


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

_RE_REPEATED_WHY = re.compile(
    r"^(?:почему|зачем|why)\b.*(?:ещё раз|again|всё же|really|seriously)", re.I
)
_RE_STRESS_MARKERS = re.compile(
    r"\bно\s+всё[- ]же\b|\bне\s+согласен\b|\bdisagree\b|\bwrong\b|\bинтересно\b", re.I
)
_RE_THEORY_CHECK = re.compile(
    r"^(?:что\s+такое|define|explain|definition)\b", re.I
)


def _compute_pressure(strategy: dict, interviewer: dict) -> float:
    """Synthesise a 0-1 pressure score from strategy + interviewer."""
    base = {"low": 0.2, "medium": 0.5, "high": 0.85}.get(
        str(strategy.get("pressure", "low")).lower(), 0.5
    )
    interviewer_p = interviewer.get("pressure_level", 0.0) if interviewer else 0.0
    # weighted average: current question 60%, session history 40%
    return round(base * 0.6 + interviewer_p * 0.4, 3)


class EmpathyNegotiationLayer:
    """Stage 7: adds empathy + negotiation hints to the pipeline item.

    Stateless apart from an optional reference to the shared InterviewerProfile
    dict (read-only at this stage — mutations happen in WhyStrategyStage).

    Call ``process(item)`` once per question.  The method is thread-safe.
    """

    def process(self, item: dict) -> dict:
        """Enrich *item* with ``_empathy_hints`` and ``_empathy_result`` keys.

        Always returns *item* — never returns None or raises.
        Falls back to a default EmpathyResult on any error.
        """
        try:
            result = self._build(item)
        except Exception:
            result = EmpathyResult(
                tone=_Tone.CALM,
                tone_trigger=_TONE_TRIGGER[_Tone.CALM],
                pressure_score=0.0,
            )
        item["_empathy_hints"]  = result.hints
        item["_empathy_result"] = result.to_dict()
        return item

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build(self, item: dict) -> EmpathyResult:
        text       = item.get("text", "")
        strategy   = item.get("_why_strategy") or {}
        interviewer = item.get("_interviewer_profile") or {}
        anchor_ctx = item.get("_anchor_context") or []

        goal        = strategy.get("goal", "general")
        answer_type = strategy.get("answer_type", "short")
        pressure    = _compute_pressure(strategy, interviewer)
        prefers_ex  = interviewer.get("prefers_examples", False)
        interrupted = interviewer.get("interrupt_count", 0) > 0
        questions_n = interviewer.get("questions_seen", 0)
        has_anchor  = bool(anchor_ctx)

        tone   = _Tone.CALM
        hints: List[str] = []
        rules:  List[str] = []
        nego_move: Optional[str] = None

        def _set_tone(candidate: str) -> None:
            """Raise tone only if candidate has strictly higher priority."""
            nonlocal tone
            if _TONE_PRIORITY[candidate] > _TONE_PRIORITY[tone]:
                tone = candidate

        # ---- Rule 1: High pressure → warm + soft opener ----
        if pressure >= 0.75:
            _set_tone(_Tone.WARM)
            hints.append(f"Используй мягкий тон (давление {pressure:.0%})")
            hints.append('Подтверди понимание: "Да, понимаю..."')
            nego_move = _SOFTENERS["opening"]
            rules.append("high_pressure_warm")

        # ---- Rule 2: Repeated / insistent WHY → grounded + bridge ----
        if _RE_REPEATED_WHY.search(text) or _RE_STRESS_MARKERS.search(text):
            _set_tone(_Tone.GROUNDED)
            hints.append("Говори только через конкретный пример — не абстрактно")
            hints.append('Используй мост: "Из своего опыта..."')
            nego_move = _SOFTENERS["bridge"]
            rules.append("repeated_why_grounded")

        # ---- Rule 3: Interrupting interviewer → be brief (highest priority) ----
        if interrupted:
            _set_tone(_Tone.BRIEF)
            hints.append("Отвечай коротко — интервьюер перебивает")
            hints.append("Одна мысль — одно предложение")
            rules.append("interviewer_interrupts_brief")

        # ---- Rule 4: Experience goal + anchor available → ground in case ----
        if goal in ("evaluate_experience", "check_experience") and has_anchor:
            _set_tone(_Tone.GROUNDED)
            hints.append("Начни с конкретного кейса из Anchor")
            hints.append("Цифры/метрики обязательны — интервьюер проверяет опыт")
            rules.append("experience_goal_with_anchor")

        # ---- Rule 5: Theory/definition question → assertive, not flat ----
        if _RE_THEORY_CHECK.search(text) or answer_type == "definition":
            _set_tone(_Tone.ASSERTIVE)
            hints.append("Дай определение — затем сразу пример из практики")
            hints.append("Не читай учебник — говори как практик")
            rules.append("theory_question_assertive")

        # ---- Rule 6: Interviewer prefers examples, question is abstract ----
        if prefers_ex and answer_type not in ("experiential",):
            hints.append("Этот интервьюер любит кейсы — добавь свой пример")
            rules.append("prefers_examples_nudge")

        # ---- Rule 7: First few questions — build rapport ----
        if 1 <= questions_n <= 3 and not rules:
            _set_tone(_Tone.WARM)
            hints.append("Начало интервью — установи контакт: краткий и уверенный ответ")
            nego_move = _SOFTENERS["redirect"]
            rules.append("rapport_building_start")

        # ---- Rule 8: Default — stay grounded ----
        if not hints:
            tone = _Tone.CALM
            hints.append("Отвечай спокойно и по делу")
            rules.append("default_calm")

        # When BRIEF wins, drop hints that contradict brevity (soft openers)
        if tone == _Tone.BRIEF:
            _brief_conflicts = {
                'Подтверди понимание: "Да, понимаю..."',
                f'Пауза допустима: "{_SOFTENERS["pause_phrase"]}"',
            }
            hints = [h for h in hints if h not in _brief_conflicts]
            nego_move = None  # don't open with a softener when brevity is key

        # Add pause-phrase for high-pressure scenarios (unless BRIEF tone won)
        elif pressure >= 0.75:
            hints.append(f'Пауза допустима: "{_SOFTENERS["pause_phrase"]}"')

        return EmpathyResult(
            tone=tone,
            tone_trigger=_TONE_TRIGGER.get(tone, _TONE_TRIGGER[_Tone.CALM]),
            hints=hints,
            negotiation_move=nego_move,
            pressure_score=pressure,
            active_rules=rules,
        )
