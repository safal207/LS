from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable


@dataclass(frozen=True)
class AuditMetrics:
    total_events: int
    gmv_ct: float
    payout_events: int
    median_payout_latency_s: float
    p95_payout_latency_s: float
    dispute_rate: float
    rollback_rate: float
    verification_pass_rate: float
    economic_efficiency_score: float


class EconomicsAudit:
    """Computes economic and reliability metrics from append-only market events."""

    def summarize(self, events: Iterable[dict[str, Any]]) -> AuditMetrics:
        rows = list(events)
        total = len(rows)
        if total == 0:
            return AuditMetrics(0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        gmv = 0.0
        payout_latencies: list[float] = []
        disputes = 0
        rollbacks = 0
        verification_pass = 0
        verification_total = 0

        created_ts_by_proposal: dict[str, int] = {}

        for event in rows:
            event_type = str(event.get("event_type", ""))
            ts = self._safe_int(event.get("ts"))
            data = event.get("data")
            if not isinstance(data, dict):
                data = {}

            proposal_id = str(data.get("proposal_id", ""))

            if event_type in {"task_created", "proposal_created"} and proposal_id and ts is not None:
                created_ts_by_proposal[proposal_id] = ts

            if event_type in {"payout_released", "settlement_completed"}:
                amount = self._safe_float(data.get("amount_ct", data.get("payout_ct", 0.0)))
                gmv += max(0.0, amount)
                if proposal_id and ts is not None and proposal_id in created_ts_by_proposal:
                    payout_latencies.append(max(0.0, float(ts - created_ts_by_proposal[proposal_id])))

            if event_type in {"task_disputed", "dispute_opened"}:
                disputes += 1

            if event_type in {"rollback_applied", "penalty_applied"}:
                rollbacks += 1

            if event_type in {"artifact_verified", "verification_completed"}:
                verification_total += 1
                verdict = str(data.get("verdict", data.get("result", ""))).lower()
                if verdict in {"verified", "pass", "accepted", "ok"}:
                    verification_pass += 1

        payout_count = len(payout_latencies)
        med_latency = median(payout_latencies) if payout_latencies else 0.0
        p95 = self._percentile(payout_latencies, 95) if payout_latencies else 0.0

        dispute_rate = disputes / total
        rollback_rate = rollbacks / total
        verification_pass_rate = (verification_pass / verification_total) if verification_total else 0.0

        efficiency = self._compute_efficiency(
            verification_pass_rate=verification_pass_rate,
            dispute_rate=dispute_rate,
            rollback_rate=rollback_rate,
            p95_latency_s=p95,
        )

        return AuditMetrics(
            total_events=total,
            gmv_ct=round(gmv, 6),
            payout_events=payout_count,
            median_payout_latency_s=round(med_latency, 6),
            p95_payout_latency_s=round(p95, 6),
            dispute_rate=round(dispute_rate, 6),
            rollback_rate=round(rollback_rate, 6),
            verification_pass_rate=round(verification_pass_rate, 6),
            economic_efficiency_score=round(efficiency, 6),
        )

    @staticmethod
    def _compute_efficiency(
        *,
        verification_pass_rate: float,
        dispute_rate: float,
        rollback_rate: float,
        p95_latency_s: float,
    ) -> float:
        latency_penalty = min(1.0, p95_latency_s / 3600.0)
        score = (
            0.5 * verification_pass_rate
            + 0.25 * (1.0 - dispute_rate)
            + 0.15 * (1.0 - rollback_rate)
            + 0.10 * (1.0 - latency_penalty)
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _percentile(samples: list[float], p: int) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        rank = (len(ordered) - 1) * (p / 100.0)
        low = int(rank)
        high = min(low + 1, len(ordered) - 1)
        frac = rank - low
        return ordered[low] * (1.0 - frac) + ordered[high] * frac
