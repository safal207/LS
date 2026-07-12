from __future__ import annotations

import json
from pathlib import Path

from ls.coordination_benchmark import (
    RouteProfile,
    apply_pareto_frontier,
    render_markdown_report,
    simulate_route,
    validate_route_result,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "multi-session-coordination"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _runs():
    scenario = _load(
        EXPERIMENT / "canonical-five-session-scenario.json"
    )
    profiles = [
        RouteProfile.from_mapping(_load(path))
        for path in sorted((EXPERIMENT / "routes").glob("*.json"))
    ]
    return apply_pareto_frontier(
        simulate_route(scenario, profile)
        for profile in profiles
    )


def test_all_route_results_validate_and_share_scenario_hash() -> None:
    runs = _runs()
    hashes = set()
    for run in runs:
        validate_route_result(run.result)
        hashes.add(run.result["scenario_hash"])

    assert len(hashes) == 1


def test_receipt_gated_route_is_only_safe_pareto_candidate() -> None:
    verdicts = {
        run.result["route_id"]: run.result["verdict"]
        for run in _runs()
    }

    assert verdicts == {
        "append-only-log": "UNSAFE_UNAUTHORIZED_EVENT",
        "human-relay": "UNSAFE_UNAUTHORIZED_EVENT",
        "receipt-gated-event-route": "SAFE_PARETO_CANDIDATE",
        "shared-mutable-state": "UNSAFE_STALE_ACTION",
    }


def test_safe_route_has_zero_safety_violations() -> None:
    safe = next(
        run
        for run in _runs()
        if run.result["route_id"] == "receipt-gated-event-route"
    )
    metrics = safe.result["metrics"]

    assert metrics["stale_action_count"] == 0
    assert metrics["dependency_violation_count"] == 0
    assert metrics["unverified_release_count"] == 0
    assert metrics["unauthorized_event_acceptance_count"] == 0
    assert metrics["duplicate_side_effect_count"] == 0


def test_safe_route_blocks_unverified_forged_and_stale_transitions() -> None:
    safe = next(
        run
        for run in _runs()
        if run.result["route_id"] == "receipt-gated-event-route"
    )
    outcomes = {item["outcome"] for item in safe.trace}

    assert "BLOCKED_MISSING_RECEIPT" in outcomes
    assert "BLOCKED_UNAUTHORIZED_PRODUCER" in outcomes
    assert "BLOCKED_STALE_GENERATION" in outcomes
    assert "DEDUPLICATED" in outcomes


def test_replacement_sessions_replay_current_generation() -> None:
    safe = next(
        run
        for run in _runs()
        if run.result["route_id"] == "receipt-gated-event-route"
    )
    actions = [
        item
        for item in safe.trace
        if item["step"] == "dependent_action"
    ]

    assert {item["session_id"] for item in actions} == {
        "database",
        "search",
        "dashboard",
    }
    assert all(
        item["outcome"] == "SAFE_ACTION"
        and item["plan_generation"] == 2
        for item in actions
    )


def test_simulation_is_deterministic() -> None:
    first = [(run.result, run.trace) for run in _runs()]
    second = [(run.result, run.trace) for run in _runs()]

    assert first == second


def test_report_keeps_safety_and_optimization_visible() -> None:
    report = render_markdown_report(_runs())

    assert (
        "Safety constraints are evaluated before optimization metrics."
        in report
    )
    assert "receipt-gated-event-route" in report
    assert "SAFE_PARETO_CANDIDATE" in report


def test_generated_summary_matches_frozen_expected_snapshot() -> None:
    actual = [
        {
            "route_id": run.result["route_id"],
            "verdict": run.result["verdict"],
            "metrics": run.result["metrics"],
        }
        for run in _runs()
    ]
    expected = _load(
        EXPERIMENT / "expected" / "benchmark-summary.json"
    )

    assert actual == expected
