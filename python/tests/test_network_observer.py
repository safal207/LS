from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from network import (  # noqa: E402
    CognitiveAdequacyCore,
    NetworkObserver,
    NetworkSnapshot,
    TemporalTrajectoryResult,
    TrajectoryRecord,
)
from retrospective import RetrospectiveReport  # noqa: E402


def _trajectory() -> TemporalTrajectoryResult:
    snapshot = NetworkSnapshot(
        snapshot_id="snapshot-observer",
        timestamp="2026-03-27T12:00:00Z",
        route_health={"count": 3, "strong": ["full_run>local>gonka>mimo"], "weak": [], "avg_quality": 0.77, "avg_latency_ms": 7800.0},
        coalition_health={"count": 1, "strong": ["full_run>local>gonka>mimo"], "weak": [], "avg_trust": 0.79},
        derived_module_health={"count": 2, "active": ["m1"], "review": [], "retired": [], "avg_trust": 0.75, "avg_quality": 0.74},
        adequacy_score=0.76,
        latency_score=0.73,
        drift_score=0.12,
    )
    record = TrajectoryRecord(
        period="test",
        previous_snapshot_id="prev",
        current_snapshot_id="snapshot-observer",
        deltas={"adequacy_delta": 0.04, "latency_delta": 0.03, "drift_delta": -0.02},
        trend="improving",
        risks=[],
        opportunities=["adequacy trend is improving"],
    )
    return TemporalTrajectoryResult(snapshot=snapshot, record=record, scenarios=[])


def test_network_observer_aggregates_all_views() -> None:
    retrospective = RetrospectiveReport(
        timestamp="now",
        strong_routes=["full_run>local>gonka>mimo"],
        recommendations=["promote strong coalitions"],
    )
    trajectory = _trajectory()
    observer = NetworkObserver(adequacy_core=CognitiveAdequacyCore())

    report = observer.evaluate(retrospective_report=retrospective, trajectory_result=trajectory)

    assert report.status == "stable"
    assert report.summary["trend"] == "improving"
    assert report.retrospective["strong_routes"] == ["full_run>local>gonka>mimo"]
    assert report.trajectory["snapshot"]["snapshot_id"] == "snapshot-observer"
    assert report.adequacy["status"] == "stable"
