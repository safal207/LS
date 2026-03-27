from __future__ import annotations

from .models import NetworkSnapshot, TrajectoryRecord


class TrajectoryAnalyzer:
    def analyze(self, previous: NetworkSnapshot | None, current: NetworkSnapshot) -> TrajectoryRecord:
        if previous is None:
            return TrajectoryRecord(
                period="bootstrap",
                previous_snapshot_id="",
                current_snapshot_id=current.snapshot_id,
                deltas={
                    "adequacy_delta": current.adequacy_score,
                    "latency_delta": current.latency_score,
                    "drift_delta": current.drift_score,
                },
                trend="bootstrap",
                risks=[],
                opportunities=["collect more trajectory data"],
            )

        adequacy_delta = round(current.adequacy_score - previous.adequacy_score, 4)
        latency_delta = round(current.latency_score - previous.latency_score, 4)
        drift_delta = round(current.drift_score - previous.drift_score, 4)

        risks: list[str] = []
        opportunities: list[str] = []
        if adequacy_delta < -0.05:
            risks.append("adequacy is degrading")
        if latency_delta < -0.05:
            risks.append("latency profile is worsening")
        if drift_delta > 0.05:
            risks.append("network drift is increasing")
        if adequacy_delta > 0.05:
            opportunities.append("adequacy trend is improving")
        if latency_delta > 0.05:
            opportunities.append("latency profile is improving")
        if drift_delta < -0.05:
            opportunities.append("network drift is decreasing")
        if not risks and not opportunities:
            opportunities.append("network state is stable")

        trend = "stable"
        if adequacy_delta > 0.03 and drift_delta <= 0:
            trend = "improving"
        elif adequacy_delta < -0.03 or drift_delta > 0.03:
            trend = "degrading"

        return TrajectoryRecord(
            period=f"{previous.timestamp}->{current.timestamp}",
            previous_snapshot_id=previous.snapshot_id,
            current_snapshot_id=current.snapshot_id,
            deltas={
                "adequacy_delta": adequacy_delta,
                "latency_delta": latency_delta,
                "drift_delta": drift_delta,
            },
            trend=trend,
            risks=risks,
            opportunities=opportunities,
        )
