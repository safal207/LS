from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MergeDecision = Literal["accept", "defer", "reject"]


@dataclass(frozen=True)
class LessonMergeResult:
    decision: MergeDecision
    score_breakdown: dict[str, float]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "score_breakdown": dict(self.score_breakdown),
            "reason": self.reason,
        }


def _token_set(value: Any) -> set[str]:
    text = str(value or "").lower()
    return {token for token in text.split() if token}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def evaluate_external_lesson_for_merge(
    lesson: dict[str, Any],
    *,
    existing_beliefs: list[dict[str, Any]] | None = None,
) -> LessonMergeResult:
    """Evaluate external lesson with lightweight quality/resonance policy.

    Policy:
    - reject: low quality or very low resonance
    - defer: medium quality/resonance
    - accept: high enough quality and resonance
    """

    existing_beliefs = existing_beliefs or []
    lesson_text = lesson.get("content") or lesson.get("lesson") or ""
    lesson_tokens = _token_set(lesson_text)

    quality = lesson.get("quality")
    if isinstance(quality, (int, float)):
        quality_score = max(0.0, min(1.0, float(quality)))
    else:
        quality_score = 0.5

    resonance_samples: list[float] = []
    for belief in existing_beliefs:
        belief_text = belief.get("content") or belief.get("lesson") or belief.get("id") or ""
        resonance_samples.append(_jaccard(lesson_tokens, _token_set(belief_text)))
    resonance = max(resonance_samples) if resonance_samples else 0.5

    coherence = 1.0 if lesson_tokens else 0.0
    final_score = (0.5 * quality_score) + (0.35 * resonance) + (0.15 * coherence)

    breakdown = {
        "quality": round(quality_score, 6),
        "resonance": round(resonance, 6),
        "coherence": round(coherence, 6),
        "final_score": round(final_score, 6),
    }

    if quality_score < 0.25 or resonance < 0.1:
        return LessonMergeResult("reject", breakdown, "low quality/resonance")
    if final_score >= 0.65:
        return LessonMergeResult("accept", breakdown, "score above accept threshold")
    return LessonMergeResult("defer", breakdown, "needs more validation")
