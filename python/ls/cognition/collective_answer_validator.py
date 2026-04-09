from __future__ import annotations

# TODO: This validator is intended to sit after shared-memory candidate generation
# and before final answer selection in the multi-agent runtime (e.g. AgentLoop).

from collections import Counter
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from ls.cognition.lifetra_validation_adapter import (
        ValidationTraceArtifact,
        ValidationTraceBackend,
    )
    from ls.cognition.validation_governance import (
        ValidationGovernanceEngine,
        ValidationGovernanceReport,
    )


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


@dataclass(frozen=True)
class ValidatedCandidate:
    agent_id: str
    accepted: bool
    score: float
    reasons: list[str]
    risk_flags: list[str]


@dataclass(frozen=True)
class ValidationResult:
    ranked_candidates: list[ValidatedCandidate]
    winner_agent_id: str | None
    consensus_status: str  # convergent | weak | conflicted | rejected
    consensus_summary: str
    global_risk_flags: list[str]
    governance_report: ValidationGovernanceReport | None = None
    trace_artifact: ValidationTraceArtifact | None = None


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

    def __init__(
        self,
        trace_backend: ValidationTraceBackend | None = None,
        governance_engine: ValidationGovernanceEngine | None = None,
    ) -> None:
        self.trace_backend = trace_backend
        self.governance_engine = governance_engine

    def validate(self, payload: ValidationInput) -> ValidationResult:
        validated = [_validate_candidate(c) for c in payload.candidates]
        # Stable sort by score desc, then by agent_id asc for explicit tie-break.
        validated.sort(key=lambda v: (-v.score, v.agent_id))

        accepted = [v for v in validated if v.accepted]
        global_risk_flags: list[str] = []

        # Echo chamber detection: look for ANY group of 3+ candidates with
        # identical normalized text whose scores are all weak (< 0.55).
        norm_texts = [_normalize_text(c.answer_text) for c in payload.candidates]
        text_counts = Counter(norm_texts)
        for text, count in text_counts.items():
            if count < self._ECHO_THRESHOLD:
                continue
            matching_scores = [
                _score(c)
                for c, t in zip(payload.candidates, norm_texts)
                if t == text
            ]
            if all(s < 0.55 for s in matching_scores):
                global_risk_flags.append("possible_echo_chamber")
                break

        # Determine consensus status and winner
        if not accepted:
            global_risk_flags.append("no_valid_candidates")
            result = ValidationResult(
                ranked_candidates=validated,
                winner_agent_id=None,
                consensus_status="rejected",
                consensus_summary="No candidates met acceptance criteria.",
                global_risk_flags=global_risk_flags,
            )
            return self._attach_trace_artifact(payload, result)

        winner = accepted[0]

        if len(accepted) == 1:
            global_risk_flags.append("single_point_consensus")
            result = ValidationResult(
                ranked_candidates=validated,
                winner_agent_id=winner.agent_id,
                consensus_status="weak",
                consensus_summary=(
                    f"Only one candidate accepted (agent={winner.agent_id}, "
                    f"score={winner.score:.3f})."
                ),
                global_risk_flags=global_risk_flags,
            )
            return self._attach_trace_artifact(payload, result)

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

        if contradiction_count > 0:
            global_risk_flags.append("conflict_between_top_candidates")
            consensus_status = "conflicted"
            summary = (
                f"Top candidates conflict (contradictions={contradiction_count}, "
                f"score_diff={score_diff:.3f})."
            )
        elif score_diff <= self._CONVERGENT_SCORE_DIFF:
            consensus_status = "convergent"
            summary = (
                f"Top two candidates converge (agent={winner.agent_id} score={winner.score:.3f}, "
                f"agent={second.agent_id} score={second.score:.3f}, diff={score_diff:.3f})."
            )
        else:
            # Multiple accepted but second is distant from the winner.
            # Not single_point_consensus (that flag is reserved for len(accepted) == 1).
            consensus_status = "weak"
            summary = (
                f"Winner clear but second candidate is distant "
                f"(score_diff={score_diff:.3f})."
            )

        result = ValidationResult(
            ranked_candidates=validated,
            winner_agent_id=winner.agent_id,
            consensus_status=consensus_status,
            consensus_summary=summary,
            global_risk_flags=global_risk_flags,
        )
        return self._attach_trace_artifact(payload, result)

    def _attach_trace_artifact(
        self,
        payload: ValidationInput,
        result: ValidationResult,
    ) -> ValidationResult:
        if self.trace_backend is None:
            trace_attached = result
        else:
            trace_artifact = self.trace_backend.build_validation_trace(payload, result)
            if trace_artifact is None:
                trace_attached = result
            else:
                trace_attached = replace(result, trace_artifact=trace_artifact)
        if self.governance_engine is None:
            return trace_attached
        governance_report = self.governance_engine.build_governance_report(payload, trace_attached)
        return replace(trace_attached, governance_report=governance_report)
