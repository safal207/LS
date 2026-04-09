from __future__ import annotations

# TODO: This validator is intended to sit after shared-memory candidate generation
# and before final answer selection in the multi-agent runtime (e.g. AgentLoop).

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CandidateAnswer:
    agent_id: str
    answer_text: str
    relevance: float = 0.0
    thread_relevance: float = 0.0
    hallucination_risk: float = 0.0
    supports: Sequence[str] = ()
    contradicts: Sequence[str] = ()


@dataclass(frozen=True)
class ValidationInput:
    task_prompt: str
    candidates: Sequence[CandidateAnswer]


@dataclass
class ValidatedCandidate:
    agent_id: str
    accepted: bool
    score: float
    reasons: list[str]
    risk_flags: list[str]


@dataclass
class ValidationResult:
    ranked_candidates: list[ValidatedCandidate]
    winner_agent_id: str | None
    consensus_status: str  # convergent | weak | conflicted | rejected
    consensus_summary: str
    global_risk_flags: list[str]


def _score(candidate: CandidateAnswer) -> float:
    raw = (
        0.4 * candidate.relevance
        + 0.3 * candidate.thread_relevance
        + 0.1 * min(len(candidate.supports), 3) / 3
        - 0.2 * candidate.hallucination_risk
        - 0.1 * min(len(candidate.contradicts), 3) / 3
    )
    return max(0.0, min(1.0, raw))


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _validate_candidate(candidate: CandidateAnswer) -> ValidatedCandidate:
    risk_flags: list[str] = []
    reasons: list[str] = []

    if not candidate.answer_text.strip():
        risk_flags.append("empty_answer")

    if candidate.relevance < 0.30:
        risk_flags.append("low_relevance")

    if candidate.thread_relevance < 0.30:
        risk_flags.append("low_thread_relevance")

    if candidate.hallucination_risk > 0.65:
        risk_flags.append("high_hallucination_risk")

    if len(candidate.contradicts) > 0:
        risk_flags.append("contradiction_pressure")

    score = _score(candidate)

    accepted = (
        score >= 0.45
        and candidate.relevance >= 0.30
        and candidate.thread_relevance >= 0.30
        and candidate.hallucination_risk <= 0.65
        and "empty_answer" not in risk_flags
    )

    if accepted:
        reasons.append(f"score={score:.3f} meets threshold")
        reasons.append(f"relevance={candidate.relevance:.2f} ok")
        reasons.append(f"thread_relevance={candidate.thread_relevance:.2f} ok")
        reasons.append(f"hallucination_risk={candidate.hallucination_risk:.2f} ok")
    else:
        if score < 0.45:
            reasons.append(f"score={score:.3f} below 0.45")
        if candidate.relevance < 0.30:
            reasons.append(f"relevance={candidate.relevance:.2f} below 0.30")
        if candidate.thread_relevance < 0.30:
            reasons.append(f"thread_relevance={candidate.thread_relevance:.2f} below 0.30")
        if candidate.hallucination_risk > 0.65:
            reasons.append(f"hallucination_risk={candidate.hallucination_risk:.2f} above 0.65")
        if "empty_answer" in risk_flags:
            reasons.append("answer text is empty")

    return ValidatedCandidate(
        agent_id=candidate.agent_id,
        accepted=accepted,
        score=score,
        reasons=reasons,
        risk_flags=risk_flags,
    )


class CollectiveAnswerValidator:
    _ECHO_THRESHOLD = 3
    _CONVERGENT_SCORE_DIFF = 0.15

    def validate(self, payload: ValidationInput) -> ValidationResult:
        validated = [_validate_candidate(c) for c in payload.candidates]
        validated.sort(key=lambda v: v.score, reverse=True)

        accepted = [v for v in validated if v.accepted]
        global_risk_flags: list[str] = []

        # Echo chamber detection
        norm_texts = [_normalize_text(c.answer_text) for c in payload.candidates]
        if len(norm_texts) >= self._ECHO_THRESHOLD:
            top_text = norm_texts[0] if norm_texts else ""
            duplicates = sum(1 for t in norm_texts if t == top_text)
            if duplicates >= self._ECHO_THRESHOLD:
                # Check if the matching candidates are all weak (score < 0.55)
                matching_scores = [
                    _score(c)
                    for c, t in zip(payload.candidates, norm_texts)
                    if t == top_text
                ]
                if all(s < 0.55 for s in matching_scores):
                    global_risk_flags.append("possible_echo_chamber")

        # Determine consensus status and winner
        if not accepted:
            global_risk_flags.append("no_valid_candidates")
            return ValidationResult(
                ranked_candidates=validated,
                winner_agent_id=None,
                consensus_status="rejected",
                consensus_summary="No candidates met acceptance criteria.",
                global_risk_flags=global_risk_flags,
            )

        winner = accepted[0]

        if len(accepted) == 1:
            global_risk_flags.append("single_point_consensus")
            return ValidationResult(
                ranked_candidates=validated,
                winner_agent_id=winner.agent_id,
                consensus_status="weak",
                consensus_summary=(
                    f"Only one candidate accepted (agent={winner.agent_id}, "
                    f"score={winner.score:.3f})."
                ),
                global_risk_flags=global_risk_flags,
            )

        second = accepted[1]
        score_diff = winner.score - second.score

        # Count cross-contradictions among accepted candidates
        accepted_ids = {v.agent_id for v in accepted}
        contradiction_count = sum(
            1
            for c in payload.candidates
            if c.agent_id in accepted_ids
            for target in c.contradicts
            if target in accepted_ids
        )

        if contradiction_count > 0 or (score_diff < 0.05 and contradiction_count > 0):
            global_risk_flags.append("conflict_between_top_candidates")
            consensus_status = "conflicted"
            summary = (
                f"Top candidates conflict (contradictions={contradiction_count}, "
                f"score_diff={score_diff:.3f})."
            )
        elif score_diff <= self._CONVERGENT_SCORE_DIFF and contradiction_count == 0:
            consensus_status = "convergent"
            summary = (
                f"Top two candidates converge (agent={winner.agent_id} score={winner.score:.3f}, "
                f"agent={second.agent_id} score={second.score:.3f}, diff={score_diff:.3f})."
            )
        else:
            consensus_status = "weak"
            global_risk_flags.append("single_point_consensus")
            summary = (
                f"Winner clear but second candidate is distant "
                f"(score_diff={score_diff:.3f})."
            )

        return ValidationResult(
            ranked_candidates=validated,
            winner_agent_id=winner.agent_id,
            consensus_status=consensus_status,
            consensus_summary=summary,
            global_risk_flags=global_risk_flags,
        )
