from __future__ import annotations

from decimal import Decimal

import pytest

from modules.cel import (
    ContributionApiError,
    ContributionLedger,
    ContributionRecord,
    distribute_value,
)


def test_contribution_score_distribution_matches_resonance_formula() -> None:
    ledger = ContributionLedger()
    proposal_id = "prop_003"
    ledger.add(
        ContributionRecord(
            proposal_id=proposal_id,
            agent_id="agent_A",
            contribution_type="hypothesis",
            impact=0.8,
            resonance=1.0,
            accuracy=0.5,
        )
    )
    ledger.add(
        ContributionRecord(
            proposal_id=proposal_id,
            agent_id="agent_B",
            contribution_type="refinement",
            impact=0.5,
            resonance=1.0,
            accuracy=0.5,
        )
    )
    ledger.add(
        ContributionRecord(
            proposal_id=proposal_id,
            agent_id="agent_C",
            contribution_type="validation",
            impact=0.4,
            resonance=1.0,
            accuracy=0.5,
        )
    )
    ledger.add(
        ContributionRecord(
            proposal_id=proposal_id,
            agent_id="agent_D",
            contribution_type="extension",
            impact=0.3,
            resonance=1.0,
            accuracy=0.5,
        )
    )

    payouts = ledger.compute_payouts(proposal_id=proposal_id, total_value=Decimal("100"))
    by_agent = {p.agent_id: p for p in payouts}

    assert by_agent["agent_A"].payout == Decimal("40.000000")
    assert by_agent["agent_B"].payout == Decimal("25.000000")
    assert by_agent["agent_C"].payout == Decimal("20.000000")
    assert by_agent["agent_D"].payout == Decimal("15.000000")

    total = sum((p.payout for p in payouts), start=Decimal("0"))
    assert total == Decimal("100.000000")


def test_zero_total_score_falls_back_to_equal_split() -> None:
    proposal_id = "prop_zero"
    payouts = distribute_value(
        proposal_id=proposal_id,
        total_value=Decimal("90"),
        contributions=[
            ContributionRecord(proposal_id, "a", "hypothesis", 0, 0, 0),
            ContributionRecord(proposal_id, "b", "refinement", 0, 0, 0),
            ContributionRecord(proposal_id, "c", "validation", 0, 0, 0),
        ],
    )

    assert len(payouts) == 3
    amounts = sorted(p.payout for p in payouts)
    assert amounts == [Decimal("30.000000"), Decimal("30.000000"), Decimal("30.000000")]


def test_rejects_invalid_metrics() -> None:
    ledger = ContributionLedger()

    with pytest.raises(ContributionApiError) as exc:
        ledger.add(
            ContributionRecord(
                proposal_id="p",
                agent_id="a",
                contribution_type="hypothesis",
                impact=-0.1,
                resonance=1,
                accuracy=1,
            )
        )

    assert exc.value.code == "INVALID_METRIC"


def test_builds_contribution_graph_projection() -> None:
    ledger = ContributionLedger()
    proposal_id = "prop_graph"
    ledger.add(ContributionRecord(proposal_id, "agent_A", "hypothesis", 1, 1, 1))
    ledger.add(ContributionRecord(proposal_id, "agent_B", "refinement", 1, 1, 1))
    ledger.add(ContributionRecord(proposal_id, "agent_C", "validation", 1, 1, 1))

    graph = ledger.contribution_graph(proposal_id)
    assert graph["hypothesis"] == ["agent_A"]
    assert graph["refinement"] == ["agent_B"]
    assert graph["validation"] == ["agent_C"]


def test_no_contributions_raises() -> None:
    ledger = ContributionLedger()
    with pytest.raises(ContributionApiError) as exc:
        ledger.compute_payouts("missing", Decimal("10"))
    assert exc.value.code == "NO_CONTRIBUTIONS"
