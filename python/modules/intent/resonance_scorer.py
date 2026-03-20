"""ResonanceScorer — Stage 9 of the SmartEar cognitive pipeline.

Computes a single ``resonance_score`` (0.0–1.0) that measures how well the
pipeline is positioned to move the conversation from dissonance to resonance.

A score of 1.0 means: low pressure, tone perfectly matched to question type,
anchor context leveraged, active de-escalation move ready, no heavy coaching
needed.  A score near 0.0 means: maximum pressure, contradictory cues, no
grounding material.

Design
------
* Pure function over the item dict — no I/O, no ML, no side effects.
* All inputs are optional — graceful fallback to neutral score (0.5).
* ``< 0.1 ms`` per call.
* Score is decomposed into named sub-scores stored in ``_resonance_detail``
  for debugging and logging.

Score formula
-------------
    base          = 1.0 − pressure × 0.5        (high pressure → low base)
    Δ tone_match  +0.10  tone × answer_type alignment
    Δ anchor      +0.10  anchor used for experiential / defense answer
    Δ nego        +0.08  active de-escalation opener present
    Δ rapport     +0.05  rapport-building rule fired (first questions)
    Δ experience  +0.05  experience goal matched anchor
    Δ intervention −0.00/−0.05/−0.12   low/medium/high coaching needed
    clamped to [0.0, 1.0]

Usage::

    scorer = ResonanceScorer()
    item = scorer.process(item)
    print(item["_resonance_score"])   # e.g. 0.87
    print(item["_resonance_detail"])  # decomposed sub-scores
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Tone × answer_type alignment pairs (good cognitive resonance indicators)
# ---------------------------------------------------------------------------

_GOOD_TONE_PAIRS: set[tuple[str, str]] = {
    ("grounded",  "experiential"),
    ("warm",      "experiential"),
    ("assertive", "definition"),
    ("assertive", "reasoning"),
    ("brief",     "short"),
    ("calm",      "short"),
    ("grounded",  "defense"),
}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class ResonanceDetail:
    """Decomposed sub-scores for one resonance computation.

    Each field is a signed float contribution to the final score.
    """
    base:         float = 0.5   # 1.0 − pressure × 0.5
    tone_match:   float = 0.0
    anchor_bonus: float = 0.0
    nego_bonus:   float = 0.0
    rapport_bonus: float = 0.0
    experience_bonus: float = 0.0
    intervention_penalty: float = 0.0
    final: float = 0.5

    def to_dict(self) -> dict:
        return {
            "base":               round(self.base, 3),
            "tone_match":         round(self.tone_match, 3),
            "anchor_bonus":       round(self.anchor_bonus, 3),
            "nego_bonus":         round(self.nego_bonus, 3),
            "rapport_bonus":      round(self.rapport_bonus, 3),
            "experience_bonus":   round(self.experience_bonus, 3),
            "intervention_penalty": round(self.intervention_penalty, 3),
            "final":              round(self.final, 3),
        }


# ---------------------------------------------------------------------------
# ResonanceScorer
# ---------------------------------------------------------------------------

class ResonanceScorer:
    """Stage 9: compute resonance_score and store it on the pipeline item.

    Always returns *item* — never raises.
    """

    def process(self, item: dict) -> dict:
        try:
            detail = self._compute(item)
        except Exception:
            detail = ResonanceDetail()
        item["_resonance_score"]  = detail.final
        item["_resonance_detail"] = detail.to_dict()
        return item

    # ------------------------------------------------------------------

    def _compute(self, item: dict) -> ResonanceDetail:
        empathy    = item.get("_empathy_result")  or {}
        strategy   = item.get("_why_strategy")    or {}
        copilot    = item.get("_copilot_output")  or {}
        anchor_ctx = item.get("_anchor_context")  or []

        pressure    = float(empathy.get("pressure_score", 0.0))
        tone        = str(empathy.get("tone", "calm"))
        answer_type = str(strategy.get("answer_type", "short"))
        intervention = str(copilot.get("intervention_level", "low"))
        active_rules = set(copilot.get("active_rules") or [])
        anchor_used  = bool(anchor_ctx)
        nego_move    = empathy.get("negotiation_move")

        d = ResonanceDetail()

        # 1. Base — inverse of pressure
        d.base = round(1.0 - pressure * 0.5, 3)

        # 2. Tone × answer_type alignment
        if (tone, answer_type) in _GOOD_TONE_PAIRS:
            d.tone_match = 0.10

        # 3. Anchor leveraged for experiential / defense content
        if anchor_used and answer_type in ("experiential", "defense", "reasoning"):
            d.anchor_bonus = 0.10

        # 4. Active de-escalation opener ready
        if nego_move:
            d.nego_bonus = 0.08

        # 5. Rapport-building (early questions go smooth)
        if "rapport_building_start" in active_rules:
            d.rapport_bonus = 0.05

        # 6. Experience goal matched with anchor
        if "experience_goal_with_anchor" in active_rules:
            d.experience_bonus = 0.05

        # 7. Intervention penalty — heavy coaching = lower resonance achieved
        d.intervention_penalty = {"low": 0.0, "medium": -0.05, "high": -0.12}.get(
            intervention, 0.0
        )

        raw = (
            d.base
            + d.tone_match
            + d.anchor_bonus
            + d.nego_bonus
            + d.rapport_bonus
            + d.experience_bonus
            + d.intervention_penalty
        )
        d.final = round(max(0.0, min(1.0, raw)), 3)
        return d
