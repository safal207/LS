# -*- coding: utf-8 -*-
"""Alignment recommendation adoption trace — per-recommendation traceability layer.

After a response is generated, checks whether each recommended action was
reflected in the final response text using a deterministic lexical signal map.
Advisory-only: never modifies recommendations, routing, graph_mode, route_key,
feedback labels, reputation scores, or any upstream pipeline state.
No LLM, no embeddings. This is a traceability layer, not a causal attribution engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Action signal registry
# Canonical action strings -> lexical cues for positive match in response text.
# Cues are short, case-insensitive substrings.  At least one cue ≥ 5 chars
# per entry to avoid spurious single-character matches.
# ---------------------------------------------------------------------------

_ACTION_SIGNAL_MAP: dict[str, list[str]] = {
    # bridge_phrase family
    "acknowledge common ground before moving forward": [
        "i understand", "we both", "common ground", "agree that",
        "i see your point", "that makes sense", "fair point",
    ],
    "name the shared concern before proposing action": [
        "shared concern", "both care", "we want", "mutual",
        "important to both", "i hear", "understand the concern",
    ],
    # pacing / structure family
    "slow response tempo and increase structural clarity": [
        "let me break", "step by step", "first,", "second,", "third,",
        "to summarize", "in short", "briefly",
    ],
    "use open-ended structure to invite co-ownership of the solution": [
        "what do you think", "your thoughts", "how does that sound",
        "open to", "together we", "collaborate",
    ],
    # framing family
    "frame solutions as shared options, not unilateral decisions": [
        "one option", "another option", "we could", "we might",
        "possible approach", "consider", "alternatively",
    ],
    "avoid winner/loser framing": [
        "not about winning", "not about who", "both benefit",
        "no winner", "together", "shared outcome",
    ],
    # dialogue invitation family
    "invite the other party to respond before concluding": [
        "what do you think", "your view", "let me know", "thoughts",
        "does that work", "how does that sound", "feedback welcome",
    ],
    # cause / background family
    "separate background cause from visible behavior": [
        "root cause", "underlying", "because of", "reason behind",
        "what caused", "origin", "source of",
    ],
    # proposal family
    "present proposal as starting point, not final answer": [
        "starting point", "not final", "open to changes", "draft",
        "initial proposal", "subject to", "feel free to adjust",
    ],
    # tension / acknowledgment family
    "acknowledge tension before proposing a fix": [
        "tension", "conflict", "challenge here", "difficult",
        "i know this is", "not easy", "acknowledge",
    ],
}

# Normalised key cache for fast lookup
_ACTION_KEYS_LOWER: dict[str, list[str]] = {
    k.lower(): v for k, v in _ACTION_SIGNAL_MAP.items()
}


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _match_recommended_action(
    action: str,
    response_text: str,
) -> dict[str, Any]:
    """Return match result for a single recommended action against response text.

    Returns:
        {matched: bool, cues_found: list[str], action_known: bool}

    Case-insensitive.  Unknown actions (not in registry) are safely treated
    as unmatched.
    """
    action_key = (action or "").lower().strip()
    cues = _ACTION_KEYS_LOWER.get(action_key)

    if cues is None:
        return {"matched": False, "cues_found": [], "action_known": False}

    response_lower = (response_text or "").lower()
    found = [cue for cue in cues if cue.lower() in response_lower]
    return {
        "matched": len(found) > 0,
        "cues_found": found,
        "action_known": True,
    }


def _label_adoption(
    matched_count: int,
    total_count: int,
) -> tuple[str, float]:
    """Return (adoption_label, adoption_score) from matched/total counts.

    adopted           matched_count == total_count and total_count > 0
    partially_adopted matched_count > 0 but < total_count
    not_adopted       matched_count == 0 or total_count == 0
    """
    if total_count == 0:
        return "not_adopted", 0.0

    ratio = matched_count / total_count
    score = round(ratio, 4)

    if matched_count == total_count:
        return "adopted", score
    if matched_count > 0:
        return "partially_adopted", score
    return "not_adopted", 0.0


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

_EXCERPT_LEN = 160


def build_recommendation_adoption_trace(
    recommendations: list[dict[str, Any]],
    response_text: str,
    alignment_outcome: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build one adoption-trace object per recommendation.

    Matches recommended_actions against response_text via deterministic lexical
    cues.  Never modifies inputs.  Never raises.
    """
    if not recommendations or not isinstance(recommendations, list):
        return []
    if not isinstance(response_text, str):
        response_text = ""

    response_lower = response_text.lower()
    excerpt = response_text[:_EXCERPT_LEN].replace("\n", " ") if response_text else ""
    ao = alignment_outcome or {}
    effect_reason = ao.get("effect_reason") or ""

    result: list[dict[str, Any]] = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue

        sid = rec.get("strategy_id") or ""
        pattern_ids = list(rec.get("based_on_pattern_ids") or [])
        actions: list[str] = list(rec.get("recommended_actions") or [])

        matched_actions: list[str] = []
        unmatched_actions: list[str] = []
        unknown_count = 0

        for action in actions:
            m = _match_recommended_action(action, response_lower)
            if not m["action_known"]:
                unknown_count += 1
                unmatched_actions.append(action)
            elif m["matched"]:
                matched_actions.append(action)
            else:
                unmatched_actions.append(action)

        total = len(actions)
        matched_count = len(matched_actions)
        label, score = _label_adoption(matched_count, total)

        if matched_count == total and total > 0:
            trace_reason = f"all {total} recommended action(s) reflected in response wording"
        elif matched_count > 0:
            trace_reason = (
                f"{matched_count} of {total} recommended action(s) "
                "reflected in response wording"
            )
        else:
            trace_reason = "no recommendation signals found in response"

        trace: dict[str, Any] = {
            "strategy_id": sid,
            "pattern_ids": pattern_ids,
            "adoption_label": label,
            "matched_actions": matched_actions,
            "unmatched_actions": unmatched_actions,
            "matched_action_count": matched_count,
            "total_action_count": total,
            "adoption_score": score,
            "effect_reason": effect_reason,
            "trace_reason": trace_reason,
            "response_excerpt": excerpt,
        }
        result.append(trace)

    return result


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_recommendation_adoption_summary(
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a compact summary over a list of adoption traces.

    Fixed-key output; JSON-serialisable.  Never raises.
    """
    empty: dict[str, Any] = {
        "total_traces": 0,
        "adopted_total": 0,
        "partially_adopted_total": 0,
        "not_adopted_total": 0,
        "avg_adoption_score": 0.0,
        "top_adopted_strategy_ids": [],
        "top_not_adopted_strategy_ids": [],
        "top_adopted_pattern_ids": [],
    }
    if not traces or not isinstance(traces, list):
        return dict(empty)

    valid = [t for t in traces if isinstance(t, dict)]
    if not valid:
        return dict(empty)

    total = len(valid)
    adopted = sum(1 for t in valid if t.get("adoption_label") == "adopted")
    partial = sum(1 for t in valid if t.get("adoption_label") == "partially_adopted")
    not_ad = sum(1 for t in valid if t.get("adoption_label") == "not_adopted")
    score_sum = sum(float(t.get("adoption_score") or 0.0) for t in valid)
    avg_score = round(score_sum / total, 4) if total else 0.0

    adopted_sid: dict[str, int] = {}
    not_ad_sid: dict[str, int] = {}
    adopted_pid: dict[str, int] = {}

    for t in valid:
        sid = t.get("strategy_id") or ""
        lbl = t.get("adoption_label") or "not_adopted"
        if sid:
            if lbl == "adopted":
                adopted_sid[sid] = adopted_sid.get(sid, 0) + 1
            elif lbl == "not_adopted":
                not_ad_sid[sid] = not_ad_sid.get(sid, 0) + 1
        if lbl == "adopted":
            for pid in (t.get("pattern_ids") or []):
                if pid:
                    adopted_pid[pid] = adopted_pid.get(pid, 0) + 1

    return {
        "total_traces": total,
        "adopted_total": adopted,
        "partially_adopted_total": partial,
        "not_adopted_total": not_ad,
        "avg_adoption_score": avg_score,
        "top_adopted_strategy_ids": [
            k for k, _ in sorted(adopted_sid.items(), key=lambda x: -x[1])[:5]
        ],
        "top_not_adopted_strategy_ids": [
            k for k, _ in sorted(not_ad_sid.items(), key=lambda x: -x[1])[:5]
        ],
        "top_adopted_pattern_ids": [
            k for k, _ in sorted(adopted_pid.items(), key=lambda x: -x[1])[:5]
        ],
    }


# ---------------------------------------------------------------------------
# Observability metrics
# ---------------------------------------------------------------------------

@dataclass
class AlignmentRecommendationAdoptionMetrics:
    calls_total: int = 0
    recommendations_processed_total: int = 0
    traces_total: int = 0
    adopted_total: int = 0
    partially_adopted_total: int = 0
    not_adopted_total: int = 0
    score_sum: float = 0.0
    action_matches_total: int = 0
    unknown_actions_total: int = 0

    @property
    def avg_adoption_score(self) -> float:
        if self.traces_total == 0:
            return 0.0
        return round(self.score_sum / self.traces_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "recommendations_processed_total": self.recommendations_processed_total,
            "traces_total": self.traces_total,
            "adopted_total": self.adopted_total,
            "partially_adopted_total": self.partially_adopted_total,
            "not_adopted_total": self.not_adopted_total,
            "avg_adoption_score": self.avg_adoption_score,
            "action_matches_total": self.action_matches_total,
            "unknown_actions_total": self.unknown_actions_total,
        }
