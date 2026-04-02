from __future__ import annotations

from retrospective import RetrospectiveCouncil, RetrospectiveReport

from .models import AdequacyReport, TuningFork
from .temporal_trajectory import TemporalTrajectoryLayer, TemporalTrajectoryResult


class CognitiveAdequacyCore:
    """Observer layer that keeps the network inside an acceptable operating envelope."""

    def __init__(
        self,
        *,
        retrospective_council: RetrospectiveCouncil | None = None,
        temporal_layer: TemporalTrajectoryLayer | None = None,
        tuning_fork: TuningFork | None = None,
    ) -> None:
        self.retrospective_council = retrospective_council or RetrospectiveCouncil()
        self.temporal_layer = temporal_layer or TemporalTrajectoryLayer()
        self.tuning_fork = tuning_fork or TuningFork()

    def evaluate(
        self,
        *,
        retrospective_report: RetrospectiveReport | None = None,
        trajectory_result: TemporalTrajectoryResult | None = None,
    ) -> AdequacyReport:
        retrospective_report = retrospective_report or self.retrospective_council.analyze()
        trajectory_result = trajectory_result or self.temporal_layer.evaluate()

        snapshot = trajectory_result.snapshot
        record = trajectory_result.record
        route_health = snapshot.route_health or {}
        coalition_health = snapshot.coalition_health or {}
        module_health = snapshot.derived_module_health or {}

        adequacy_gap = round(snapshot.adequacy_score - self.tuning_fork.adequacy_target, 4)
        latency_gap = round(snapshot.latency_score - self.tuning_fork.latency_target, 4)
        drift_gap = round(snapshot.drift_score - self.tuning_fork.drift_ceiling, 4)

        route_count = int(route_health.get("count", 0) or 0)
        strong_routes = list(route_health.get("strong", []) or [])
        weak_routes = list(retrospective_report.weak_routes or [])
        stale_modules = list(retrospective_report.stale_modules or [])
        weak_coalitions = list(retrospective_report.weak_coalitions or [])

        route_dominance_risk = route_count >= 3 and len(strong_routes) == 1 and adequacy_gap < 0
        coalition_inflation_risk = (
            float(coalition_health.get("avg_trust", 0.0) or 0.0) > snapshot.adequacy_score + 0.12
            or (bool(retrospective_report.strong_coalitions) and bool(weak_coalitions))
        )
        module_drift_risk = (
            snapshot.drift_score > self.tuning_fork.drift_ceiling
            or len(stale_modules) > self.tuning_fork.stale_module_limit
            or bool(module_health.get("review"))
        )

        risks: list[str] = []
        recommendations: list[str] = []

        if adequacy_gap < 0:
            risks.append("adequacy below tuning fork")
            recommendations.append("reduce trust for routes or modules that lower answer adequacy")
        if latency_gap < 0:
            risks.append("latency below tuning fork")
            recommendations.append("prefer cheaper routes for routine questions or raise reuse")
        if drift_gap > 0:
            risks.append("drift above ceiling")
            recommendations.append("run care cycles and review derived modules before further promotion")
        if route_dominance_risk:
            risks.append("route dominance risk")
            recommendations.append("increase exploration to avoid overfitting the network to one route")
        if coalition_inflation_risk:
            risks.append("coalition trust inflation")
            recommendations.append("require coalition trust to track adequacy, not just repeated use")
        if module_drift_risk:
            risks.append("derived module drift")
            recommendations.append("demote or retire stale derived modules and refresh parent coalitions")
        if len(weak_routes) > self.tuning_fork.weak_route_limit:
            risks.append("too many weak routes")
            recommendations.append("prune weak routes from preferred path selection")

        for recommendation in retrospective_report.recommendations:
            if recommendation not in recommendations:
                recommendations.append(recommendation)

        severe_risks = sum(
            1
            for flag in (
                adequacy_gap < -0.08,
                drift_gap > 0.08,
                route_dominance_risk,
                coalition_inflation_risk,
                module_drift_risk,
            )
            if flag
        )
        if severe_risks >= 2 or record.trend == "degrading":
            status = "intervene"
        elif risks:
            status = "watch"
        else:
            status = "stable"
            if not recommendations:
                recommendations.append("network is inside the tuning fork; continue collecting evidence")

        observer_summary = {
            "trend": record.trend,
            "snapshot_id": snapshot.snapshot_id,
            "route_count": route_count,
            "weak_route_count": len(weak_routes),
            "strong_route_count": len(strong_routes),
            "stale_module_count": len(stale_modules),
            "weak_coalition_count": len(weak_coalitions),
        }

        return AdequacyReport(
            status=status,
            adequacy_gap=adequacy_gap,
            latency_gap=latency_gap,
            drift_gap=drift_gap,
            route_dominance_risk=route_dominance_risk,
            coalition_inflation_risk=coalition_inflation_risk,
            module_drift_risk=module_drift_risk,
            risks=risks,
            recommendations=recommendations,
            observer_summary=observer_summary,
            tuning_fork=self.tuning_fork.to_dict(),
        )
