from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from network import (  # noqa: E402
    CognitiveAdequacyCore,
    NetworkSnapshot,
    TemporalTrajectoryResult,
    TrajectoryRecord,
)
from retrospective import RetrospectiveReport  # noqa: E402


def _trajectory(*, adequacy: float, latency: float, drift: float, trend: str = "stable") -> TemporalTrajectoryResult:
    snapshot = NetworkSnapshot(
        snapshot_id="snapshot-test",
        timestamp="2026-03-27T10:00:00Z",
        route_health={
            "count": 4,
            "strong": ["full_run>local>gonka>mimo"],
            "weak": ["full_run>cloud"],
            "avg_quality": adequacy,
            "avg_latency_ms": 8200.0,
        },
        coalition_health={
            "count": 2,
            "strong": ["full_run>local>gonka>mimo"],
            "weak": ["full_run>cloud"],
            "avg_trust": 0.82,
        },
        derived_module_health={
            "count": 3,
            "active": ["m1", "m2"],
            "review": ["m3"] if drift > 0.35 else [],
            "retired": [],
            "avg_trust": 0.76,
            "avg_quality": adequacy,
        },
        adequacy_score=adequacy,
        latency_score=latency,
        drift_score=drift,
    )
    record = TrajectoryRecord(
        period="test",
        previous_snapshot_id="snapshot-prev",
        current_snapshot_id="snapshot-test",
        deltas={"adequacy_delta": 0.0, "latency_delta": 0.0, "drift_delta": 0.0},
        trend=trend,
        risks=[] if trend != "degrading" else ["adequacy is degrading"],
        opportunities=[],
    )
    return TemporalTrajectoryResult(snapshot=snapshot, record=record, scenarios=[])


def test_cognitive_adequacy_stable_when_within_tuning_fork() -> None:
    core = CognitiveAdequacyCore()
    report = core.evaluate(
        retrospective_report=RetrospectiveReport(timestamp="now", strong_routes=["full_run>local>gonka>mimo"]),
        trajectory_result=_trajectory(adequacy=0.78, latency=0.74, drift=0.10),
    )

    assert report.status == "stable"
    assert report.route_dominance_risk is False
    assert report.module_drift_risk is False


def test_cognitive_adequacy_intervenes_on_drift_and_degrading_trend() -> None:
    core = CognitiveAdequacyCore()
    report = core.evaluate(
        retrospective_report=RetrospectiveReport(
            timestamp="now",
            weak_routes=["full_run>cloud", "full_run>local"],
            weak_coalitions=["full_run>cloud"],
            stale_modules=["derived-1", "derived-2"],
        ),
        trajectory_result=_trajectory(adequacy=0.52, latency=0.40, drift=0.66, trend="degrading"),
    )

    assert report.status == "intervene"
    assert report.module_drift_risk is True
    assert "drift above ceiling" in report.risks
    assert report.observer_summary["stale_module_count"] == 2
