from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clamp(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class CouncilGoal:
    type: str
    summary: str


@dataclass(frozen=True)
class CouncilNetworkContext:
    route_candidates: list[str] = field(default_factory=list)
    active_nodes: list[str] = field(default_factory=list)
    graph_state_version: str = "unknown"


@dataclass(frozen=True)
class CouncilParticipant:
    model_id: str
    model_type: str
    proposal_id: str
    proposal_summary: str
    route_hint: str
    confidence: float
    latency_ms: int
    token_cost: float = 0.0
    selected: bool = False
    weight_in_final_decision: float = 0.0

    def normalized_confidence(self) -> float:
        return _clamp(float(self.confidence))

    def normalized_latency_score(self) -> float:
        if self.latency_ms <= 0:
            return 1.0
        return _clamp(1.0 - (float(self.latency_ms) / 10_000.0))

    def normalized_cost_score(self) -> float:
        if self.token_cost <= 0:
            return 1.0
        return _clamp(1.0 - (float(self.token_cost) / 0.25))


@dataclass(frozen=True)
class CouncilDecision:
    selected_route: str
    decision_summary: str
    derived_from_proposals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CouncilOutcome:
    success: bool
    path_quality: float
    network_improvement: float
    operator_intervention_required: bool
    operator_feedback_score: float
    drift_detected: bool
    receiver_type: str = "unknown"
    receiver_resonance_score: float = 0.0
    receiver_acceptance_label: str = "unknown"

    def success_score(self) -> float:
        return 1.0 if self.success else 0.0

    def intervention_score(self) -> float:
        return 0.0 if self.operator_intervention_required else 1.0

    def drift_score(self) -> float:
        return 0.0 if self.drift_detected else 1.0

    def resonance_score(self) -> float:
        return _clamp(self.receiver_resonance_score)


@dataclass(frozen=True)
class CouncilContributionBreakdown:
    model_id: str
    adoption_score: float
    outcome_lift: float
    stability_impact: float
    receiver_resonance: float
    cost_efficiency: float
    total_contribution_score: float


@dataclass(frozen=True)
class CouncilAttribution:
    best_contributor_model_id: str
    best_contributor_score: float
    contribution_breakdown: list[CouncilContributionBreakdown] = field(default_factory=list)


@dataclass(frozen=True)
class CouncilContributionLedger:
    cycle_id: str
    task_id: str
    timestamp: str
    goal: CouncilGoal
    network_context: CouncilNetworkContext
    participants: list[CouncilParticipant]
    final_decision: CouncilDecision
    outcome: CouncilOutcome
    attribution: CouncilAttribution

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def build(
        cls,
        *,
        cycle_id: str,
        task_id: str,
        goal: CouncilGoal,
        network_context: CouncilNetworkContext,
        participants: list[CouncilParticipant],
        final_decision: CouncilDecision,
        outcome: CouncilOutcome,
        timestamp: str | None = None,
    ) -> "CouncilContributionLedger":
        attribution = build_council_attribution(
            participants=participants,
            final_decision=final_decision,
            outcome=outcome,
        )
        return cls(
            cycle_id=cycle_id,
            task_id=task_id,
            timestamp=timestamp or _utc_now_iso(),
            goal=goal,
            network_context=network_context,
            participants=participants,
            final_decision=final_decision,
            outcome=outcome,
            attribution=attribution,
        )


def build_council_attribution(
    *,
    participants: list[CouncilParticipant],
    final_decision: CouncilDecision,
    outcome: CouncilOutcome,
) -> CouncilAttribution:
    breakdown: list[CouncilContributionBreakdown] = []
    best_model_id = ""
    best_score = -1.0

    for participant in participants:
        adopted = participant.selected or participant.proposal_id in final_decision.derived_from_proposals
        route_match = 1.0 if participant.route_hint == final_decision.selected_route else 0.0

        adoption_score = _clamp(
            (0.6 if adopted else 0.0)
            + (0.2 * route_match)
            + (0.2 * _clamp(participant.weight_in_final_decision))
        )

        outcome_lift = _clamp(
            (0.45 * outcome.success_score())
            + (0.3 * _clamp(outcome.path_quality))
            + (0.25 * _clamp(outcome.network_improvement))
        )

        stability_impact = _clamp(
            (0.35 * outcome.drift_score())
            + (0.25 * outcome.intervention_score())
            + (0.20 * _clamp(outcome.operator_feedback_score))
            + (0.20 * outcome.resonance_score())
        )

        receiver_resonance = outcome.resonance_score()

        cost_efficiency = _clamp(
            (0.45 * participant.normalized_latency_score())
            + (0.35 * participant.normalized_cost_score())
            + (0.20 * participant.normalized_confidence())
        )

        total = _clamp(
            (0.30 * adoption_score)
            + (0.25 * outcome_lift)
            + (0.20 * stability_impact)
            + (0.15 * receiver_resonance)
            + (0.15 * cost_efficiency)
        )

        record = CouncilContributionBreakdown(
            model_id=participant.model_id,
            adoption_score=round(adoption_score, 4),
            outcome_lift=round(outcome_lift, 4),
            stability_impact=round(stability_impact, 4),
            receiver_resonance=round(receiver_resonance, 4),
            cost_efficiency=round(cost_efficiency, 4),
            total_contribution_score=round(total, 4),
        )
        breakdown.append(record)

        if record.total_contribution_score > best_score:
            best_model_id = record.model_id
            best_score = record.total_contribution_score

    return CouncilAttribution(
        best_contributor_model_id=best_model_id,
        best_contributor_score=round(max(best_score, 0.0), 4),
        contribution_breakdown=breakdown,
    )
