from __future__ import annotations

import copy
import json
from pathlib import Path

from ls.coordination_benchmark import (
    build_manifest,
    generate_safe_dry_run,
    load_records,
    verify_pilot,
    write_record,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = (
    ROOT
    / "experiments"
    / "multi-session-coordination"
    / "canonical-five-session-scenario.json"
)


def _scenario() -> dict:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


def _manifest() -> dict:
    return build_manifest(_scenario(), run_id="pilot-test-001")


def _records() -> list[dict]:
    traces = generate_safe_dry_run(_manifest())
    return [
        copy.deepcopy(record)
        for session_records in traces.values()
        for record in session_records
    ]


def test_safe_dry_run_confirms_receipt_gated_route() -> None:
    result = verify_pilot(_manifest(), _records())

    assert result["verdict"] == "PASS_SAFE_ROUTE_CONFIRMED"
    assert result["violations"] == []
    assert result["metrics"] == {
        "record_count": 38,
        "session_count": 5,
        "blocked_adversarial_event_count": 6,
        "deduplicated_event_count": 3,
        "recovered_session_count": 2,
        "safe_action_count": 3,
    }


def test_missing_session_is_inconclusive() -> None:
    records = [
        record for record in _records() if record["session_id"] != "dashboard"
    ]

    result = verify_pilot(_manifest(), records)

    assert result["verdict"] == "INCONCLUSIVE_MISSING_SESSION"
    assert result["violations"] == ["missing session trace: dashboard"]


def test_sequence_gap_is_inconclusive() -> None:
    records = _records()
    records = [
        record
        for record in records
        if not (
            record["session_id"] == "database"
            and record["record_type"] == "EVENT_DEDUPLICATED"
        )
    ]

    result = verify_pilot(_manifest(), records)

    assert result["verdict"] == "INCONCLUSIVE_TRACE_GAP"
    assert "sequence must be contiguous" in result["violations"][0]


def test_unbound_record_is_inconclusive() -> None:
    records = _records()
    records[0]["scenario_hash"] = "sha256:" + ("0" * 64)

    result = verify_pilot(_manifest(), records)

    assert result["verdict"] == "INCONCLUSIVE_UNBOUND_TRACE"
    assert "scenario_hash" in result["violations"][0]


def test_stale_action_fails() -> None:
    records = _records()
    action = next(
        record
        for record in records
        if record["session_id"] == "database"
        and record["record_type"] == "ACTION_EXECUTED"
    )
    action["generation"] = 1

    result = verify_pilot(_manifest(), records)

    assert result["verdict"] == "FAIL_STALE_ACTION"


def test_unverified_action_fails() -> None:
    records = _records()
    action = next(
        record
        for record in records
        if record["session_id"] == "database"
        and record["record_type"] == "ACTION_EXECUTED"
    )
    action["details"]["receipt_status"] = "NOT_RUN"

    result = verify_pilot(_manifest(), records)

    assert result["verdict"] == "FAIL_UNVERIFIED_RELEASE"


def test_missing_forged_event_block_fails() -> None:
    records = _records()
    forged = _manifest()["forged_event_id"]
    target = next(
        record
        for record in records
        if record["session_id"] == "database"
        and record.get("event_id") == forged
    )
    target["event_id"] = "evt-unrelated"

    result = verify_pilot(_manifest(), records)

    assert result["verdict"] == "FAIL_UNAUTHORIZED_EVENT"


def test_duplicate_side_effect_fails() -> None:
    records = _records()
    duplicate = next(
        record
        for record in records
        if record["session_id"] == "database"
        and record["record_type"] == "EVENT_DEDUPLICATED"
    )
    duplicate["record_type"] = "PLAN_INVALIDATED"
    duplicate["record_id"] = (
        f"database:{duplicate['sequence']}:PLAN_INVALIDATED"
    )

    result = verify_pilot(_manifest(), records)

    assert result["verdict"] == "FAIL_DUPLICATE_EFFECT"


def test_session_owned_jsonl_round_trip(tmp_path: Path) -> None:
    manifest = _manifest()
    traces = generate_safe_dry_run(manifest)
    trace_dir = tmp_path / "traces"
    for session_records in traces.values():
        for record in session_records:
            write_record(trace_dir, record)

    loaded = load_records(trace_dir, manifest)
    result = verify_pilot(manifest, loaded)

    assert len(list(trace_dir.glob("*.jsonl"))) == 5
    assert result["verdict"] == "PASS_SAFE_ROUTE_CONFIRMED"
