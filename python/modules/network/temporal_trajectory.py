from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .future_planner import FuturePlanner
from .models import FutureScenario, NetworkSnapshot, TrajectoryRecord
from .trajectory_analyzer import TrajectoryAnalyzer
from .trajectory_store import TrajectoryStore


@dataclass
class TemporalTrajectoryResult:
    snapshot: NetworkSnapshot
    record: TrajectoryRecord
    scenarios: list[FutureScenario]

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "record": self.record.to_dict(),
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }


class TemporalTrajectoryLayer:
    def __init__(
        self,
        *,
        store: TrajectoryStore | None = None,
        analyzer: TrajectoryAnalyzer | None = None,
        planner: FuturePlanner | None = None,
    ) -> None:
        self.store = store or TrajectoryStore()
        self.analyzer = analyzer or TrajectoryAnalyzer()
        self.planner = planner or FuturePlanner()

    def evaluate(self) -> TemporalTrajectoryResult:
        previous_snapshots = self.store.list_snapshots()
        previous = previous_snapshots[-1] if previous_snapshots else None
        current = self.store.capture_snapshot()
        record = self.analyzer.analyze(previous, current)
        scenarios = self.planner.build_scenarios(current, record)
        return TemporalTrajectoryResult(snapshot=current, record=record, scenarios=scenarios)
