from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.cel import OutcomeSettlementWorker, SettlementError, SettlementRequest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "ctl_event_v1.schema.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_settlement_emits_valid_ctl_event_and_cem_event() -> None:
    ctl_events: list[dict] = []
    cem_events: list[dict] = []

    worker = OutcomeSettlementWorker(
        append_ctl_event=ctl_events.append,
        publish_cem_event=cem_events.append,
    )

    result = worker.settle(
        SettlementRequest(
            trace_id="trace_settle_1",
            proposal_id="prop_003",
            agent_id="energy-98231",
            expected_delta=0.05,
            actual_delta=0.07,
            horizon_sec=604800,
        )
    )

    assert result.proposal_id == "prop_003"
    assert result.result == "hit"
    assert result.error_band == 0.02
    assert result.quality_score == 0.98

    assert len(ctl_events) == 1
    schema = _load_json(SCHEMA_PATH)
    Draft202012Validator(schema).validate(ctl_events[0])
    assert ctl_events[0]["data"]["agent_id"] == "energy-98231"

    assert len(cem_events) == 1
    assert cem_events[0]["event_type"] == "settlement_completed"


def test_settlement_miss_case() -> None:
    worker = OutcomeSettlementWorker()
    result = worker.settle(
        SettlementRequest(
            trace_id="trace_settle_2",
            proposal_id="prop_004",
            agent_id="energy-98231",
            expected_delta=0.05,
            actual_delta=-0.01,
            horizon_sec=86400,
        )
    )

    assert result.result == "miss"
    assert result.error_band == 0.06
    assert result.quality_score == 0.94


def test_settlement_rejects_invalid_horizon() -> None:
    worker = OutcomeSettlementWorker()
    with pytest.raises(SettlementError) as exc:
        worker.settle(
            SettlementRequest(
                trace_id="trace_settle_3",
                proposal_id="prop_005",
                agent_id="energy-98231",
                expected_delta=0.01,
                actual_delta=0.02,
                horizon_sec=0,
            )
        )

    assert exc.value.code == "INVALID_HORIZON"
