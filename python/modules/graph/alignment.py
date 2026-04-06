from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, (list, tuple, set)):
        output: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                output.append(text)
        return output
    return [str(value).strip()] if str(value).strip() else []


@dataclass
class InteractionParticipant:
    participant_id: str
    participant_type: str = "human"
    role: str = ""
    intent: str = ""
    why: str = ""
    background_state: list[str] = field(default_factory=list)
    foreground_expression: list[str] = field(default_factory=list)
    need_vector: list[str] = field(default_factory=list)
    tension_signal: float = 0.0
    resonance_signal: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "InteractionParticipant":
        data = dict(payload or {})
        return cls(
            participant_id=str(data.get("participant_id") or data.get("id") or "unknown"),
            participant_type=str(data.get("participant_type") or "human"),
            role=str(data.get("role") or ""),
            intent=str(data.get("intent") or ""),
            why=str(data.get("why") or ""),
            background_state=_as_str_list(data.get("background_state")),
            foreground_expression=_as_str_list(data.get("foreground_expression")),
            need_vector=_as_str_list(data.get("need_vector")),
            tension_signal=float(data.get("tension_signal", 0.0) or 0.0),
            resonance_signal=float(data.get("resonance_signal", 0.0) or 0.0),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class InteractionAlignmentReport:
    alignment_score: float = 0.0
    tension_score: float = 0.0
    mismatch_reasons: list[str] = field(default_factory=list)
    agreement_reasons: list[str] = field(default_factory=list)
    dominant_axis: str = "neutral"
    suggested_mode: str = "steady"
    requires_softening: bool = False
    requires_clarification: bool = False
    requires_grounding: bool = False
    pairwise_hotspots: list[dict[str, Any]] = field(default_factory=list)
    participants: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InteractionAlignmentAnalyzer:
    """Minimal heuristic analyzer for participant alignment/tension."""

    _PRESSURE_CONFLICTS: dict[str, set[str]] = {
        "urgency": {"stability", "slow"},
        "control": {"autonomy"},
        "autonomy": {"control"},
        "speed": {"accuracy", "care"},
    }

    def analyze(
        self,
        participants: list[dict[str, Any] | str] | None,
        *,
        context: dict[str, Any] | None = None,
    ) -> InteractionAlignmentReport:
        normalized = self._normalize(participants or [])
        if len(normalized) < 2:
            return InteractionAlignmentReport(
                alignment_score=0.0,
                tension_score=0.0,
                dominant_axis="insufficient-participants",
                suggested_mode="clarify",
                requires_clarification=True,
                participants=[p.to_dict() for p in normalized],
                metadata={"heuristic_version": "alignment-mvp-v1", "context": dict(context or {})},
            )

        pairwise_hotspots: list[dict[str, Any]] = []
        mismatch_reasons: set[str] = set()
        agreement_reasons: set[str] = set()
        align_total = 0.0
        tension_total = 0.0
        pair_count = 0

        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                pair_count += 1
                pair = self._pairwise(normalized[i], normalized[j])
                align_total += pair["alignment"]
                tension_total += pair["tension"]
                mismatch_reasons.update(pair["mismatch_reasons"])
                agreement_reasons.update(pair["agreement_reasons"])
                if pair["has_evidence"] and (
                    pair["tension"] >= 0.45
                    or bool(pair["mismatch_reasons"])
                ):
                    pairwise_hotspots.append(pair)

        alignment_score = round(min(1.0, align_total / max(1, pair_count)), 3)
        tension_score = round(min(1.0, tension_total / max(1, pair_count)), 3)
        dominant_axis = "balanced"
        if tension_score >= alignment_score + 0.15:
            dominant_axis = "tension"
        elif alignment_score >= tension_score + 0.15:
            dominant_axis = "alignment"

        requires_softening = tension_score >= 0.55
        requires_clarification = bool(mismatch_reasons) and alignment_score < 0.55
        requires_grounding = tension_score >= 0.40 and alignment_score < 0.45
        suggested_mode = self._suggested_mode(
            dominant_axis=dominant_axis,
            requires_softening=requires_softening,
            requires_clarification=requires_clarification,
            requires_grounding=requires_grounding,
        )

        return InteractionAlignmentReport(
            alignment_score=alignment_score,
            tension_score=tension_score,
            mismatch_reasons=sorted(mismatch_reasons),
            agreement_reasons=sorted(agreement_reasons),
            dominant_axis=dominant_axis,
            suggested_mode=suggested_mode,
            requires_softening=requires_softening,
            requires_clarification=requires_clarification,
            requires_grounding=requires_grounding,
            pairwise_hotspots=pairwise_hotspots,
            participants=[p.to_dict() for p in normalized],
            metadata={"heuristic_version": "alignment-mvp-v1", "context": dict(context or {})},
        )

    def _normalize(self, participants: list[dict[str, Any] | str]) -> list[InteractionParticipant]:
        normalized: list[InteractionParticipant] = []
        for index, raw in enumerate(participants):
            if isinstance(raw, str):
                normalized.append(
                    InteractionParticipant(
                        participant_id=raw or f"participant-{index + 1}",
                        metadata={"source": "string"},
                    )
                )
                continue
            payload = dict(raw or {})
            if "participant_id" not in payload and "id" not in payload:
                payload["participant_id"] = f"participant-{index + 1}"
            normalized.append(InteractionParticipant.from_dict(payload))
        return normalized

    def _pairwise(self, left: InteractionParticipant, right: InteractionParticipant) -> dict[str, Any]:
        agreement_reasons: list[str] = []
        mismatch_reasons: list[str] = []
        alignment = 0.15
        tension = 0.05
        has_evidence = False

        if left.intent and right.intent and left.intent == right.intent:
            alignment += 0.25
            agreement_reasons.append(f"shared_intent:{left.intent}")
            has_evidence = True
        elif left.intent and right.intent and left.intent != right.intent:
            tension += 0.20
            mismatch_reasons.append(f"intent_conflict:{left.intent}!={right.intent}")
            has_evidence = True

        if left.why and right.why and left.why == right.why:
            alignment += 0.20
            agreement_reasons.append(f"shared_why:{left.why}")
            has_evidence = True
        elif left.why and right.why and left.why != right.why:
            tension += 0.18
            mismatch_reasons.append("why_mismatch")
            has_evidence = True

        shared_needs = set(left.need_vector).intersection(right.need_vector)
        if shared_needs:
            alignment += min(0.25, 0.08 * len(shared_needs))
            agreement_reasons.append(f"shared_needs:{','.join(sorted(shared_needs))}")
            has_evidence = True

        pressure_conflict = self._detect_pressure_conflict(left.need_vector, right.need_vector)
        if pressure_conflict:
            tension += 0.22
            mismatch_reasons.append(f"need_pressure_conflict:{pressure_conflict}")
            has_evidence = True

        expression_overlap = set(left.foreground_expression).intersection(right.foreground_expression)
        if expression_overlap:
            alignment += 0.08
            agreement_reasons.append("foreground_overlap")
            has_evidence = True

        unresolved_background = set(left.background_state).symmetric_difference(right.background_state)
        if unresolved_background and not shared_needs:
            tension += 0.08
            mismatch_reasons.append("background_state_divergence")
            has_evidence = True

        tension += min(0.20, (left.tension_signal + right.tension_signal) * 0.15)
        alignment += min(0.10, (left.resonance_signal + right.resonance_signal) * 0.10)

        return {
            "participants": [left.participant_id, right.participant_id],
            "alignment": round(min(1.0, alignment), 3),
            "tension": round(min(1.0, tension), 3),
            "mismatch_reasons": mismatch_reasons,
            "agreement_reasons": agreement_reasons,
            "has_evidence": has_evidence,
        }

    def _detect_pressure_conflict(self, left_needs: list[str], right_needs: list[str]) -> str:
        left = {n.lower() for n in left_needs}
        right = {n.lower() for n in right_needs}
        for need in left:
            opposite = self._PRESSURE_CONFLICTS.get(need, set())
            clash = opposite.intersection(right)
            if clash:
                return f"{need}<->{sorted(clash)[0]}"
        for need in right:
            opposite = self._PRESSURE_CONFLICTS.get(need, set())
            clash = opposite.intersection(left)
            if clash:
                return f"{need}<->{sorted(clash)[0]}"
        return ""

    @staticmethod
    def _suggested_mode(
        *,
        dominant_axis: str,
        requires_softening: bool,
        requires_clarification: bool,
        requires_grounding: bool,
    ) -> str:
        if requires_softening:
            return "soften-and-clarify"
        if requires_grounding:
            return "ground-and-clarify"
        if requires_clarification:
            return "clarify-goals"
        if dominant_axis == "alignment":
            return "collaborative-advance"
        return "steady"


__all__ = [
    "InteractionAlignmentAnalyzer",
    "InteractionAlignmentReport",
    "InteractionParticipant",
]
