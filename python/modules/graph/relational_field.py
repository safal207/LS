from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models import RelationalFieldSnapshot


class RelationalFieldAnalyzer:
    """Heuristic-only analyzer for interaction field signals.

    MVP constraints:
    - no routing / backend decisions
    - no auto-repair
    - no LLM/ML inference
    """

    _TENSION_MARKERS: tuple[str, ...] = (
        "никогда",
        "всегда",
        "должен",
        "должна",
        "опять",
        "невозможно",
        "бесполезно",
        "хватит",
        "прекрати",
        "устал",
        "устала",
        "не могу",
        "can't",
        "always",
        "never",
        "must",
        "again",
        "impossible",
    )
    _NEGATION_MARKERS: tuple[str, ...] = (
        "не ",
        "нет",
        "ни ",
        "без",
        "not ",
        "no ",
        "never",
    )
    _CONFLICT_MARKERS: tuple[str, ...] = (
        "!",
        "??",
        "зачем ты",
        "твоя вина",
        "это твоя",
        "ты не",
        "почему ты",
        "you are wrong",
        "your fault",
        "stop",
    )
    _ALIGNMENT_MARKERS: tuple[str, ...] = (
        "я понимаю",
        "давай вместе",
        "нам важно",
        "я слышу",
        "хочу понять",
        "let's",
        "i hear you",
        "i understand",
        "we can",
        "together",
    )

    _BACKGROUND_RULES: dict[str, tuple[str, ...]] = {
        "fear": ("боюсь", "страшно", "fear", "afraid"),
        "overload": ("перегруз", "устал", "too much", "overwhelmed"),
        "urgency": ("срочно", "немедленно", "urgent", "asap", "прямо сейчас"),
        "hurt": ("больно", "обидно", "hurt", "wounded"),
        "uncertainty": ("не уверен", "сомневаюсь", "uncertain", "not sure"),
        "control_loss": ("не контрол", "теряю контроль", "out of control", "не могу управлять"),
    }

    _FOREGROUND_RULES: dict[str, tuple[str, ...]] = {
        "attack": ("ты виноват", "обвин", "attack", "blame", "wrong"),
        "withdrawal": ("молчу", "не хочу говорить", "withdraw", "leave me"),
        "defensiveness": ("я не виноват", "это не я", "defensive", "оправдываюсь"),
        "pressure": ("должен", "сделай сейчас", "must", "now", "немедленно"),
        "appeal": ("помоги", "прошу", "please", "help me"),
        "repair_attempt": ("давай вместе", "я слышу", "прости", "sorry", "i understand"),
    }

    def analyze(
        self,
        *,
        text: str,
        participants: list[str] | None = None,
        interaction_scope: str = "human-human",
        context: dict[str, Any] | None = None,
    ) -> RelationalFieldSnapshot:
        raw = str(text or "")
        lowered = raw.lower()

        tension_score = self._compute_tension(lowered)
        alignment_score = self._compute_alignment(lowered)
        background = self._detect_tags(lowered, self._BACKGROUND_RULES)
        foreground = self._detect_tags(lowered, self._FOREGROUND_RULES)

        dominant_signal = self._dominant_signal(
            tension_score=tension_score,
            alignment_score=alignment_score,
            foreground=foreground,
            background=background,
        )
        notes = self._build_notes(
            tension_score=tension_score,
            alignment_score=alignment_score,
            dominant_signal=dominant_signal,
            foreground=foreground,
            background=background,
        )

        return RelationalFieldSnapshot(
            field_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            participants=list(participants or []),
            interaction_scope=interaction_scope,
            tension_score=tension_score,
            alignment_score=alignment_score,
            dominant_signal=dominant_signal,
            background_pressure=background,
            foreground_expression=foreground,
            notes=notes,
            metadata={
                "heuristic_version": "mvp-v1",
                "text_length": len(raw),
                "context": dict(context or {}),
            },
        )

    def _compute_tension(self, lowered: str) -> float:
        if not lowered.strip():
            return 0.0

        markers = sum(lowered.count(marker) for marker in self._TENSION_MARKERS)
        negations = sum(lowered.count(marker) for marker in self._NEGATION_MARKERS)
        conflicts = sum(lowered.count(marker) for marker in self._CONFLICT_MARKERS)

        score = markers * 0.12 + negations * 0.06 + conflicts * 0.14
        if lowered.count("!") >= 2:
            score += 0.08
        return round(min(score, 1.0), 3)

    def _compute_alignment(self, lowered: str) -> float:
        if not lowered.strip():
            return 0.0
        markers = sum(lowered.count(marker) for marker in self._ALIGNMENT_MARKERS)
        collaborative_pronouns = lowered.count("мы") + lowered.count("we ")
        score = markers * 0.2 + collaborative_pronouns * 0.05
        return round(min(score, 1.0), 3)

    @staticmethod
    def _detect_tags(lowered: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
        tags: list[str] = []
        for tag, markers in rules.items():
            if any(marker in lowered for marker in markers):
                tags.append(tag)
        return tags

    @staticmethod
    def _dominant_signal(
        *,
        tension_score: float,
        alignment_score: float,
        foreground: list[str],
        background: list[str],
    ) -> str:
        if tension_score >= max(0.55, alignment_score + 0.2):
            return "tension"
        if alignment_score >= max(0.55, tension_score + 0.15):
            return "alignment"
        if foreground:
            return f"foreground:{foreground[0]}"
        if background:
            return f"background:{background[0]}"
        return "neutral"

    @staticmethod
    def _build_notes(
        *,
        tension_score: float,
        alignment_score: float,
        dominant_signal: str,
        foreground: list[str],
        background: list[str],
    ) -> str:
        return (
            "heuristic_observation="
            f"dominant={dominant_signal}; tension={tension_score:.2f}; "
            f"alignment={alignment_score:.2f}; foreground={','.join(foreground) or 'none'}; "
            f"background={','.join(background) or 'none'}"
        )


__all__ = ["RelationalFieldSnapshot", "RelationalFieldAnalyzer"]
