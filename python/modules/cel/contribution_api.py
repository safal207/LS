from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from threading import RLock
from typing import Iterable


class ContributionApiError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ContributionRecord:
    proposal_id: str
    agent_id: str
    contribution_type: str
    impact: float
    resonance: float
    accuracy: float


@dataclass(frozen=True)
class ContributionPayout:
    agent_id: str
    score: Decimal
    share: Decimal
    payout: Decimal


class ContributionLedger:
    """Tracks contribution graph edges and computes payout split.

    Contribution Score = impact * resonance * accuracy

    Note: multiple contribution types from the same agent are intentionally
    aggregated for payout; role granularity remains available via
    ``contribution_graph()``.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, list[ContributionRecord]] = {}

    def add(self, record: ContributionRecord) -> None:
        if not record.proposal_id:
            raise ContributionApiError("INVALID_PROPOSAL_ID", "proposal_id is required")
        if not record.agent_id:
            raise ContributionApiError("INVALID_AGENT_ID", "agent_id is required")

        for name, value in (
            ("impact", record.impact),
            ("resonance", record.resonance),
            ("accuracy", record.accuracy),
        ):
            if value < 0:
                raise ContributionApiError("INVALID_METRIC", f"{name} must be >= 0")

        with self._lock:
            self._records.setdefault(record.proposal_id, []).append(record)

    def list_for_proposal(self, proposal_id: str) -> list[ContributionRecord]:
        with self._lock:
            return list(self._records.get(proposal_id, []))

    def compute_payouts(self, proposal_id: str, total_value: Decimal) -> list[ContributionPayout]:
        if total_value <= 0:
            raise ContributionApiError("INVALID_TOTAL_VALUE", "total_value must be > 0")

        records = self.list_for_proposal(proposal_id)
        if not records:
            raise ContributionApiError("NO_CONTRIBUTIONS", "no contributions for proposal")

        scored: list[tuple[str, Decimal]] = []
        for rec in records:
            score = Decimal(str(rec.impact)) * Decimal(str(rec.resonance)) * Decimal(str(rec.accuracy))
            scored.append((rec.agent_id, score))

        aggregated: dict[str, Decimal] = {}
        for agent_id, score in scored:
            aggregated[agent_id] = aggregated.get(agent_id, Decimal("0")) + score

        total_score = sum(aggregated.values(), start=Decimal("0"))
        if total_score <= 0:
            payouts: list[ContributionPayout] = []
            agents = sorted(aggregated.keys())
            base_payout = (total_value / Decimal(len(agents))).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
            distributed_payout = Decimal("0")
            for idx, agent_id in enumerate(agents):
                payout = base_payout
                if idx == len(agents) - 1:
                    payout = (total_value - distributed_payout).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                distributed_payout += payout
                share = (payout / total_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                payouts.append(
                    ContributionPayout(agent_id=agent_id, score=Decimal("0"), share=share, payout=payout)
                )
            return payouts

        payouts = []
        cumulative = Decimal("0")
        items = sorted(aggregated.items(), key=lambda x: x[0])
        for idx, (agent_id, score) in enumerate(items):
            share = (score / total_score).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            if idx == len(items) - 1:
                share = Decimal("1") - cumulative
            cumulative += share
            payout = (total_value * share).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            payouts.append(ContributionPayout(agent_id=agent_id, score=score, share=share, payout=payout))

        return payouts

    def contribution_graph(self, proposal_id: str) -> dict[str, list[str]]:
        """Simple graph projection grouped by contribution_type."""
        with self._lock:
            records = self._records.get(proposal_id, [])
            graph: dict[str, list[str]] = {}
            for rec in records:
                graph.setdefault(rec.contribution_type, []).append(rec.agent_id)
            return graph


def distribute_value(
    proposal_id: str,
    total_value: Decimal,
    contributions: Iterable[ContributionRecord],
) -> list[ContributionPayout]:
    ledger = ContributionLedger()
    for record in contributions:
        if record.proposal_id != proposal_id:
            raise ContributionApiError("MIXED_PROPOSAL_IDS", "all contributions must match proposal_id")
        ledger.add(record)
    return ledger.compute_payouts(proposal_id, total_value)
