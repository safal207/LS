from ls.cognition import (
    CouncilContributionLedger,
    CouncilDecision,
    CouncilGoal,
    CouncilNetworkContext,
    CouncilOutcome,
    CouncilParticipant,
    build_council_attribution,
)


def test_build_council_attribution_prefers_selected_route_with_strong_outcome():
    participants = [
        CouncilParticipant(
            model_id="local-qwen",
            model_type="local",
            proposal_id="p1",
            proposal_summary="Use fast local route",
            route_hint="route_a",
            confidence=0.82,
            latency_ms=800,
            token_cost=0.0,
            selected=True,
            weight_in_final_decision=0.55,
        ),
        CouncilParticipant(
            model_id="web-gpt",
            model_type="web",
            proposal_id="p2",
            proposal_summary="Use remote route",
            route_hint="route_b",
            confidence=0.91,
            latency_ms=3200,
            token_cost=0.11,
            selected=False,
            weight_in_final_decision=0.22,
        ),
    ]
    decision = CouncilDecision(
        selected_route="route_a",
        decision_summary="Pick route_a with local-first reasoning",
        derived_from_proposals=["p1"],
    )
    outcome = CouncilOutcome(
        success=True,
        path_quality=0.88,
        network_improvement=0.16,
        operator_intervention_required=False,
        operator_feedback_score=0.93,
        drift_detected=False,
        receiver_type="human_operator",
        receiver_resonance_score=0.91,
        receiver_acceptance_label="accepted",
    )

    attribution = build_council_attribution(
        participants=participants,
        final_decision=decision,
        outcome=outcome,
    )

    assert attribution.best_contributor_model_id == "local-qwen"
    assert len(attribution.contribution_breakdown) == 2
    assert attribution.best_contributor_score > 0.7


def test_ledger_build_serializes_core_sections():
    ledger = CouncilContributionLedger.build(
        cycle_id="cycle-001",
        task_id="task-001",
        goal=CouncilGoal(type="decision", summary="Choose best graph route"),
        network_context=CouncilNetworkContext(
            route_candidates=["route_a", "route_b"],
            active_nodes=["memory.redis", "operator.intent"],
            graph_state_version="v1",
        ),
        participants=[
            CouncilParticipant(
                model_id="local-qwen",
                model_type="local",
                proposal_id="p1",
                proposal_summary="Use route_a",
                route_hint="route_a",
                confidence=0.8,
                latency_ms=700,
                selected=True,
                weight_in_final_decision=0.6,
            )
        ],
        final_decision=CouncilDecision(
            selected_route="route_a",
            decision_summary="Route_a selected",
            derived_from_proposals=["p1"],
        ),
        outcome=CouncilOutcome(
            success=True,
            path_quality=0.84,
            network_improvement=0.18,
            operator_intervention_required=False,
            operator_feedback_score=0.9,
            drift_detected=False,
            receiver_type="human_operator",
            receiver_resonance_score=0.89,
            receiver_acceptance_label="accepted",
        ),
        timestamp="2026-04-07T10:30:00Z",
    )

    payload = ledger.to_dict()

    assert payload["cycle_id"] == "cycle-001"
    assert payload["goal"]["type"] == "decision"
    assert payload["network_context"]["route_candidates"] == ["route_a", "route_b"]
    assert payload["participants"][0]["model_id"] == "local-qwen"
    assert payload["final_decision"]["selected_route"] == "route_a"
    assert payload["outcome"]["receiver_type"] == "human_operator"
    assert payload["outcome"]["receiver_acceptance_label"] == "accepted"
    assert payload["attribution"]["best_contributor_model_id"] == "local-qwen"
