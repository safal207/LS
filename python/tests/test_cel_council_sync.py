from __future__ import annotations

from modules.cel import (
    ContributionLedger,
    ReputationEngine,
    apply_council_ledger_to_cel,
    build_contribution_records_from_council_ledger,
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
        cycle_id="cycle-cel-1",
        task_id="task-cel-1",
        goal=CouncilGoal(type="coordination_cycle", summary="Pick the best route"),
        network_context=CouncilNetworkContext(
            route_candidates=["route_a", "route_b"],
            active_nodes=["party:a", "party:b"],
            graph_state_version="reuse",
        ),
        participants=[
            CouncilParticipant(
                model_id="strategy:bridge-1",
                model_type="advisory_strategy",
                proposal_id="bridge-1",
                proposal_summary="Bridge with common ground",
                route_hint="route_a",
                confidence=0.8,
                latency_ms=1000,
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
            path_quality=0.85,
            network_improvement=0.22,
            operator_intervention_required=False,
            operator_feedback_score=0.88,
            drift_detected=False,
            receiver_type="human_operator",
            receiver_resonance_score=0.91,
            receiver_acceptance_label="accepted",
        ),
        timestamp="2026-04-07T12:00:00Z",
    )


def test_build_contribution_records_from_council_ledger():
    records = build_contribution_records_from_council_ledger(_ledger())

    assert len(records) == 2
    assert all(record.proposal_id == "cycle-cel-1" for record in records)
    assert {record.agent_id for record in records} == {"strategy:bridge-1", "openai:gpt-test"}
    assert all(record.resonance > 0 for record in records)


def test_apply_council_ledger_to_cel_updates_contribution_and_reputation():
    ledger = _ledger()
    contribution_ledger = ContributionLedger()
    reputation_engine = ReputationEngine()

    sync = apply_council_ledger_to_cel(
        ledger,
        contribution_ledger=contribution_ledger,
        reputation_engine=reputation_engine,
    )

    assert sync["proposal_id"] == "cycle-cel-1"
    assert sync["quality_score"] > 0.7
    assert len(sync["contribution_records"]) == 2
    assert len(sync["reputation_updates"]) == 2
    assert contribution_ledger.list_for_proposal("cycle-cel-1")
    assert reputation_engine.get("strategy:bridge-1").updates_count == 1
