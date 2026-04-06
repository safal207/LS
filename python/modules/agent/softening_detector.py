# -*- coding: utf-8 -*-
"""
Softening / de-escalation signal detector.

Observability-only layer — results are advisory and MUST NOT influence
route selection, graph mode, reuse/refine/full-run decisions, or backend choice.

Design constraints:
- rule-based, deterministic, no ML/LLM
- language-agnostic: structural + limited bilingual markers (RU/EN)
- each signal is named and logged → explainable
- cheap: single linear pass over lowercased text
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Signal categories ─────────────────────────────────────────────────────────

# Collaborative framing: "let's", "вместе", "we can", etc.
_BRIDGE_PHRASES: tuple[str, ...] = (
    # EN
    "let's", "let us", "we can", "we could", "together", "join",
    "collaborate", "i'm with you", "i am with you", "on our side",
    # RU
    "давай", "давайте", "вместе", "мы можем", "мы могли бы",
    "предлагаю вместе", "давайте вместе",
)

# Acknowledgment: "i understand", "я слышу", etc.
_ACKNOWLEDGMENT_PHRASES: tuple[str, ...] = (
    # EN
    "i understand", "i hear you", "i hear that", "i see your point",
    "that makes sense", "fair point", "i get it", "i get that",
    "you're right", "you are right", "good point",
    # RU
    "я понимаю", "я слышу", "я слышу тебя", "понимаю тебя",
    "ты прав", "ты права", "это логично", "согласен", "согласна",
    "хорошая точка", "резонно",
)

# Proposal / non-imperative framing: "perhaps", "maybe", "i suggest", etc.
_PROPOSAL_PHRASES: tuple[str, ...] = (
    # EN
    "perhaps", "maybe", "what if", "one option", "another approach",
    "i suggest", "i'd suggest", "i would suggest", "consider",
    "could we", "would you", "how about", "what about",
    # RU
    "возможно", "может быть", "что если", "предлагаю", "рассмотрим",
    "вариант", "один из вариантов", "как насчёт", "что если мы",
)

# Pacing / sequencing: "first let's", "сначала", etc.
_PACING_PHRASES: tuple[str, ...] = (
    # EN
    "first,", "firstly,", "to start,", "let me", "to begin",
    "step by step", "one step", "before we",
    # RU
    "сначала", "для начала", "для начала давай", "начнём с",
    "шаг за шагом", "прежде чем", "перед тем как",
)

# Dialogue invitation: ends with "?" or explicit invite phrases
_INVITE_PHRASES: tuple[str, ...] = (
    # EN
    "what do you think", "does that work", "would that help",
    "does this make sense", "your thoughts", "sound good",
    # RU
    "как тебе", "как вам", "что думаешь", "что думаете",
    "подходит?", "устроит?", "звучит?",
)

# Adversarial markers — if present, cap the softening score
_ADVERSARIAL_PHRASES: tuple[str, ...] = (
    # EN
    "you must", "you have to", "you need to do", "wrong!", "you're wrong",
    "stop it", "absolutely not", "never mind", "forget it",
    # RU
    "ты должен", "ты должна", "делай немедленно", "это неправильно!",
    "никогда", "нет смысла", "прекрати",
)

_SIGNAL_TABLES = {
    "bridge_phrase":      _BRIDGE_PHRASES,
    "acknowledgment":     _ACKNOWLEDGMENT_PHRASES,
    "proposal_framing":   _PROPOSAL_PHRASES,
    "pacing_marker":      _PACING_PHRASES,
    "dialogue_invitation": _INVITE_PHRASES,
}


# ── Result contract ───────────────────────────────────────────────────────────

@dataclass
class SofteningAnalysis:
    """
    Immutable observability result — never used for routing.

    Fields
    ------
    softening_detected : bool
        True when the response carries cooperative / de-escalating signals.
    score : float
        Confidence 0.0–1.0. Advisory only; not exposed to path selector.
    signals : list[str]
        Named categories that fired, e.g. ["bridge_phrase", "acknowledgment"].
        No duplicates.
    reason : str | None
        Human-readable explanation for logs / dashboard.
    """
    softening_detected: bool
    score: float
    signals: list[str] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "softening_detected": self.softening_detected,
            "score": round(self.score, 3),
            "signals": list(self.signals),
            "reason": self.reason,
        }


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_softening_signals(text: str) -> SofteningAnalysis:
    """
    Detect cooperative / softening signals in *text*.

    Deterministic, O(n) in text length × marker count.
    Language-agnostic: uses structural + bilingual (RU/EN) marker set.

    Returns
    -------
    SofteningAnalysis — advisory result, MUST NOT affect routing.
    """
    if not text or not text.strip():
        return SofteningAnalysis(
            softening_detected=False,
            score=0.0,
            signals=[],
            reason="empty_input",
        )

    lowered = text.lower()

    # Check for adversarial markers — cap scoring if found
    adversarial_hit = any(phrase in lowered for phrase in _ADVERSARIAL_PHRASES)

    # Structural signals
    ends_with_question = lowered.rstrip().endswith("?")
    word_count = len(text.split())
    is_substantial = word_count >= 20  # not a curt dismissal

    fired: list[str] = []

    for signal_name, phrases in _SIGNAL_TABLES.items():
        if any(phrase in lowered for phrase in phrases):
            fired.append(signal_name)

    # Structural signals appended last (not from phrase tables)
    if ends_with_question:
        fired.append("dialogue_invitation_structural")
    if is_substantial and not fired:
        # Substantial response with no hostile markers gets minimal credit
        pass  # do not auto-fire on length alone

    # Remove duplicates (preserve order)
    seen: set[str] = set()
    deduped: list[str] = []
    for s in fired:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    # Score: each unique signal category adds 0.25, capped at 1.0
    raw_score = len(deduped) * 0.25
    if adversarial_hit:
        raw_score = min(raw_score, 0.2)  # adversarial presence caps score
    score = round(min(raw_score, 1.0), 3)

    detected = score >= 0.25 and not adversarial_hit

    reason = _build_reason(deduped, adversarial_hit, detected)

    return SofteningAnalysis(
        softening_detected=detected,
        score=score,
        signals=deduped,
        reason=reason,
    )


def _build_reason(
    signals: list[str],
    adversarial_hit: bool,
    detected: bool,
) -> str | None:
    if adversarial_hit:
        return "adversarial_markers_present"
    if not signals:
        return "no_cooperative_signals_detected"
    label = ", ".join(signals)
    if detected:
        return f"cooperative_signals_fired: {label}"
    return f"signals_present_but_below_threshold: {label}"
