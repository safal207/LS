from __future__ import annotations

from modules.cel import (
    build_merit_updates_from_council_ledger,
    merit_score_from_council_ledger,
    network_effect_bonus,
)
from ls.cognition import (
    CouncilContributionLedger,
    CouncilDecision,
    CouncilGoal,
    CouncilNetworkContext,
    CouncilOutcome,
    CouncilParticipant,
)


def _ledger() -> CouncilContributionLedger:
    return CouncilContributionLedger.build(
        cycle_id="cycle-merit-1",
        task_id="task-merit-1",
        goal=CouncilGoal(type="coordination_cycle", summary="Align on route"),
        network_context=CouncilNetworkContext(
            route_candidates=["route_a", "route_b"],
            active_nodes=["party:a", "party:b", "party:c"],
            graph_state_version="reuse",
        ),
        participants=[
            CouncilParticipant(
                model_id="strategy:bridge-1",
                model_type="advisory_strategy",
                proposal_id="bridge-1",
                proposal_summary="Bridge common ground",
                route_hint="route_a",
                confidence=0.82,
                latency_ms=800,
                selected=True,
                weight_in_final_decision=0.7,
            ),
            CouncilParticipant(
                model_id="openai:gpt-test",
                model_type="primary_llm",
                proposal_id="route:route_a",
                proposal_summary="Primary answer",
                route_hint="route_a",
                confidence=0.9,
                latency_ms=1200,
                selected=True,
                weight_in_final_decision=1.0,
            ),
        ],
        final_decision=CouncilDecision(
            selected_route="route_a",
            decision_summary="Route A selected",
            derived_from_proposals=["bridge-1", "route:route_a"],
        ),
        outcome=CouncilOutcome(
            success=True,
            path_quality=0.86,
            network_improvement=0.2,
            operator_intervention_required=False,
            operator_feedback_score=0.9,
            drift_detected=False,
            receiver_type="human_operator",
            receiver_resonance_score=0.92,
            receiver_acceptance_label="accepted",
        ),
        timestamp="2026-04-07T12:00:00Z",
    )


def test_network_effect_bonus_is_capped():
    bonus = network_effect_bonus(verified_given=10, verified_received=10, total_tasks_last_24h=1)
    assert bonus == 0.15


def test_merit_score_from_council_ledger_returns_weighted_components():
    merit = merit_score_from_council_ledger(
        _ledger(),
        quality_score=0.88,
        contribution_score=0.76,
        trust_multiplier=1.05,
        total_tasks_last_24h=4,
    )

    assert merit["merit_score"] > 0.7
    assert merit["network_effect_bonus"] > 0
    assert merit["alignment_score"] > 0.8


def test_build_merit_updates_from_council_ledger_returns_one_update_per_participant():
    updates = build_merit_updates_from_council_ledger(_ledger(), quality_score=0.88, total_tasks_last_24h=4)

    assert len(updates) == 2
    assert {update["model_id"] for update in updates} == {"strategy:bridge-1", "openai:gpt-test"}
    assert all(float(update["merit_score"]) > 0 for update in updates)
