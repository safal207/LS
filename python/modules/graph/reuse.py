from __future__ import annotations

from .models import ReuseDecision, RetrievedCase


def decide_reuse(
    match: RetrievedCase | None,
    *,
    reuse_threshold: float = 0.92,
    refine_threshold: float = 0.78,
) -> ReuseDecision:
    if match is None:
        return ReuseDecision(
            mode="full_run",
            matched_case_id=None,
            similarity=0.0,
            reason="no-similar-case",
        )

    if match.similarity >= reuse_threshold:
        return ReuseDecision(
            mode="reuse",
            matched_case_id=match.case.case_id,
            similarity=match.similarity,
            reason=f"high-similarity ({match.reason})",
        )

    if match.similarity >= refine_threshold:
        return ReuseDecision(
            mode="refine",
            matched_case_id=match.case.case_id,
            similarity=match.similarity,
            reason=f"partial-match ({match.reason})",
        )

    return ReuseDecision(
        mode="full_run",
        matched_case_id=match.case.case_id,
        similarity=match.similarity,
        reason=f"similarity-too-low ({match.reason})",
    )
