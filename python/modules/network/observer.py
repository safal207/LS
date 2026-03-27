from __future__ import annotations

from retrospective import RetrospectiveCouncil, RetrospectiveReport

from .cognitive_adequacy import CognitiveAdequacyCore
from .models import ObserverReport
from .temporal_trajectory import TemporalTrajectoryLayer, TemporalTrajectoryResult


class NetworkObserver:
    """Aggregates retrospective, temporal, and adequacy views into one report."""

    def __init__(
        self,
        *,
        retrospective_council: RetrospectiveCouncil | None = None,
        temporal_layer: TemporalTrajectoryLayer | None = None,
        adequacy_core: CognitiveAdequacyCore | None = None,
    ) -> None:
        self.retrospective_council = retrospective_council or RetrospectiveCouncil()
        self.temporal_layer = temporal_layer or TemporalTrajectoryLayer()
        self.adequacy_core = adequacy_core or CognitiveAdequacyCore(
            retrospective_council=self.retrospective_council,
            temporal_layer=self.temporal_layer,
        )

    def evaluate(
        self,
        *,
        retrospective_report: RetrospectiveReport | None = None,
        trajectory_result: TemporalTrajectoryResult | None = None,
    ) -> ObserverReport:
        retrospective_report = retrospective_report or self.retrospective_council.analyze()
        trajectory_result = trajectory_result or self.temporal_layer.evaluate()
        adequacy_report = self.adequacy_core.evaluate(
            retrospective_report=retrospective_report,
            trajectory_result=trajectory_result,
        )

        summary = {
            "trend": trajectory_result.record.trend,
            "strong_routes": len(retrospective_report.strong_routes),
            "weak_routes": len(retrospective_report.weak_routes),
            "stale_modules": len(retrospective_report.stale_modules),
            "future_scenarios": len(trajectory_result.scenarios),
        }

        return ObserverReport(
            retrospective=retrospective_report.to_dict(),
            trajectory=trajectory_result.to_dict(),
            adequacy=adequacy_report.to_dict(),
            status=adequacy_report.status,
            summary=summary,
        )
