from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Sequence


@dataclass(frozen=True)
class TriSignalInput:
    utterance: str
    task_intent: str = ""
    recent_memory: Sequence[str] = ()
    scene_context: str = ""


@dataclass(frozen=True)
class TriSignalResult:
    agreement_signal: str
    desire_signal: str
    meaning_signal: str
    agreement_confidence: float
    desire_confidence: float
    meaning_confidence: float
    supporting_markers: dict[str, list[str]]
    tension_flags: list[str]
    summary: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _Marker:
    phrase: str
    pattern: re.Pattern[str]
    direct: bool


class TriSignalCore:
    _CONFIDENCE_DIRECT = 0.8
    _CONFIDENCE_SUPPORTING = 0.6
    _CONFIDENCE_NEUTRAL = 0.3

    _AGREEMENT_POSITIVE = (
        _Marker("да", re.compile(r"\bда\b"), True),
        _Marker("соглас", re.compile(r"соглас"), False),
        _Marker("верно", re.compile(r"верно"), True),
        _Marker("ok", re.compile(r"\bok\b"), True),
        _Marker("yes", re.compile(r"\byes\b"), True),
        _Marker("true", re.compile(r"\btrue\b"), True),
    )
    _AGREEMENT_NEGATIVE = (
        _Marker("нет", re.compile(r"\bнет\b"), True),
        _Marker("не соглас", re.compile(r"не\s+соглас"), True),
        _Marker("wrong", re.compile(r"\bwrong\b"), True),
        _Marker("false", re.compile(r"\bfalse\b"), True),
        _Marker("no", re.compile(r"\bno\b"), True),
    )

    _DESIRE_POSITIVE = (
        _Marker("хочу", re.compile(r"\bхочу\b"), True),
        _Marker("интересно", re.compile(r"интересно"), True),
        _Marker("тянет", re.compile(r"\bтянет\b"), True),
        _Marker("want", re.compile(r"\bwant\b"), True),
        _Marker("desire", re.compile(r"\bdesire\b"), True),
    )
    _DESIRE_NEGATIVE = (
        _Marker("не хочу", re.compile(r"не\s+хочу"), True),
        _Marker("не тянет", re.compile(r"не\s+тянет"), True),
        _Marker("отталкивает", re.compile(r"отталкива"), False),
        _Marker("dont want", re.compile(r"\bdon[’']?t\s+want\b"), True),
        _Marker("avoid", re.compile(r"\bavoid\b"), True),
    )

    _MEANING_POSITIVE = (
        _Marker("есть смысл", re.compile(r"есть\s+смысл"), True),
        _Marker("важно", re.compile(r"важно"), True),
        _Marker("имеет смысл", re.compile(r"имеет\s+смысл"), True),
        _Marker("meaningful", re.compile(r"\bmeaningful\b"), True),
        _Marker("worth it", re.compile(r"\bworth\s+it\b"), True),
    )
    _MEANING_NEGATIVE = (
        _Marker("нет смысла", re.compile(r"нет\s+смысла"), True),
        _Marker("бессмыс", re.compile(r"бессмыс"), False),
        _Marker("пусто", re.compile(r"\bпусто\b"), True),
        _Marker("meaningless", re.compile(r"\bmeaningless\b"), True),
        _Marker("pointless", re.compile(r"\bpointless\b"), True),
    )

    def detect(self, payload: TriSignalInput) -> TriSignalResult:
        corpus = self._build_corpus(payload)

        agreement_signal, agreement_confidence, agreement_markers = self._detect_axis(
            corpus,
            positive_markers=self._AGREEMENT_POSITIVE,
            negative_markers=self._AGREEMENT_NEGATIVE,
            positive_label="yes",
            negative_label="no",
        )
        desire_signal, desire_confidence, desire_markers = self._detect_axis(
            corpus,
            positive_markers=self._DESIRE_POSITIVE,
            negative_markers=self._DESIRE_NEGATIVE,
            positive_label="want",
            negative_label="dont_want",
        )
        meaning_signal, meaning_confidence, meaning_markers = self._detect_axis(
            corpus,
            positive_markers=self._MEANING_POSITIVE,
            negative_markers=self._MEANING_NEGATIVE,
            positive_label="meaningful",
            negative_label="meaningless",
        )

        tension_flags = self._build_tension_flags(agreement_signal, desire_signal, meaning_signal)

        return TriSignalResult(
            agreement_signal=agreement_signal,
            desire_signal=desire_signal,
            meaning_signal=meaning_signal,
            agreement_confidence=agreement_confidence,
            desire_confidence=desire_confidence,
            meaning_confidence=meaning_confidence,
            supporting_markers={
                "agreement": agreement_markers,
                "desire": desire_markers,
                "meaning": meaning_markers,
            },
            tension_flags=tension_flags,
            summary=self._build_summary(agreement_signal, desire_signal, meaning_signal),
        )

    def _build_corpus(self, payload: TriSignalInput) -> str:
        parts = [payload.utterance, payload.task_intent, payload.scene_context, *payload.recent_memory]
        return "\n".join(part for part in parts if part).lower()

    def _detect_axis(
        self,
        text: str,
        *,
        positive_markers: tuple[_Marker, ...],
        negative_markers: tuple[_Marker, ...],
        positive_label: str,
        negative_label: str,
    ) -> tuple[str, float, list[str]]:
        negative_hits, negative_direct = self._find_markers(text, negative_markers)
        if negative_hits:
            confidence = self._CONFIDENCE_DIRECT if negative_direct else self._CONFIDENCE_SUPPORTING
            return negative_label, self._clamp01(confidence), negative_hits

        positive_hits, positive_direct = self._find_markers(text, positive_markers)
        if positive_hits:
            confidence = self._CONFIDENCE_DIRECT if positive_direct else self._CONFIDENCE_SUPPORTING
            return positive_label, self._clamp01(confidence), positive_hits

        return "neutral", self._clamp01(self._CONFIDENCE_NEUTRAL), []

    def _find_markers(self, text: str, markers: tuple[_Marker, ...]) -> tuple[list[str], bool]:
        hits: list[str] = []
        has_direct = False
        for marker in markers:
            if marker.pattern.search(text):
                hits.append(marker.phrase)
                has_direct = has_direct or marker.direct
        return hits, has_direct

    def _build_tension_flags(self, agreement_signal: str, desire_signal: str, meaning_signal: str) -> list[str]:
        flags: list[str] = []
        if agreement_signal == "yes" and desire_signal == "dont_want":
            flags.append("agreement_desire_mismatch")
        if desire_signal == "want" and meaning_signal == "meaningless":
            flags.append("desire_meaning_mismatch")
        if agreement_signal == "yes" and meaning_signal == "meaningless":
            flags.append("agreement_meaning_mismatch")
        if agreement_signal == "neutral" and desire_signal == "neutral" and meaning_signal == "neutral":
            flags.append("triple_neutral")
        return flags

    def _build_summary(self, agreement_signal: str, desire_signal: str, meaning_signal: str) -> str:
        if agreement_signal == desire_signal == meaning_signal == "neutral":
            return "No clear agreement, desire, or meaning signal detected."

        agreement_text = {
            "yes": "Agrees",
            "no": "Disagrees",
            "neutral": "Neutral on agreement",
        }[agreement_signal]
        desire_text = {
            "want": "wants it",
            "dont_want": "does not want",
            "neutral": "is neutral in desire",
        }[desire_signal]
        meaning_text = {
            "meaningful": "sees meaning",
            "meaningless": "sees no meaning",
            "neutral": "is neutral on meaning",
        }[meaning_signal]

        return f"{agreement_text}, {desire_text}, and {meaning_text}."

    def _clamp01(self, value: float) -> float:
        return max(0.0, min(1.0, value))
