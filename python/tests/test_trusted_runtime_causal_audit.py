from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.adapters.cml import CMLConfig, CMLCausalAuditAdapter
from modules.trusted_runtime.causal import (
    CausalAuditDisabledError,
    CausalAuditTimeoutError,
    CausalAuthorizationBlocked,
    CausalRecord,
    DeterministicCausalAuditAdapter,
    MalformedCausalAuditResponseError,
    attach_causal_audit,
    causal_audit_event,
    require_valid_causal_ancestry,
    trail_to_causal_records,
)
from modules.trusted_runtime.contracts import (
    CognitiveTrail,
    ReusableArtifact,
    TrailEvent,
    TrailEventType,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/causal"
REPORT_SCHEMA = ROOT / "schemas/trusted_runtime/causal_audit_report.schema.json"
ARTIFACT_SCHEMA = ROOT / "schemas/trusted_runtime/reusable_artifact.schema.json"
CREATED_AT = "2026-06-23T10:00:00Z"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _records(fixture: dict) -> tuple[CausalRecord, ...]:
    return tuple(CausalRecord.from_mapping(item) for item in fixture["records"])


def _audit_fixture(name: str):
    fixture = _load(name)
    return DeterministicCausalAuditAdapter().audit_records(
        _records(fixture),
        task_id=fixture["task_id"],
        trail_id=fixture["trail_id"],
        actor="adapter:test",
        created_at=CREATED_AT,
    )


def _schema_errors(schema_path: Path, payload: dict) -> list:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return list(Draft202012Validator(schema).iter_errors(payload))


def _valid_trail() -> CognitiveTrail:
    events = (
        TrailEvent(
            event_id="event-plan",
            task_id="task-trail-001",
            trail_id="trail-001",
            event_type=TrailEventType.PLAN_CREATED,
            actor="agent:planner",
            created_at=CREATED_AT,
            parent_cause="task-trail-001",
            payload={"delegation_ref": "delegate-reviewer"},
        ),
        TrailEvent(
            event_id="event-route",
            task_id="task-trail-001",
            trail_id="trail-001",
            event_type=TrailEventType.ROUTE_SELECTED,
            actor="runtime:ls",
            created_at=CREATED_AT,
            parent_cause="event-plan",
            payload={"role_id": "reviewer", "route_id": "route-reviewer"},
        ),
        TrailEvent(
            event_id="event-authorization",
            task_id="task-trail-001",
            trail_id="trail-001",
            event_type=TrailEventType.AUTHORIZATION_ISSUED,
            actor="runtime:ls",
            created_at=CREATED_AT,
            parent_cause="event-route",
            evidence_refs=("evidence-review-001",),
            payload={
                "approval_ref": "approval-human-001",
                "scope": ["artifact:write"],
            },
        ),
    )
    return CognitiveTrail(
        task_id="task-trail-001",
        trail_id="trail-001",
        actor="human:owner",
        created_at=CREATED_AT,
        events=events,
    )


def test_trail_mapping_preserves_parent_delegation_approval_and_evidence() -> None:
    records = trail_to_causal_records(_valid_trail())

    assert records[0].record_id == "task-trail-001"
    assert records[0].permitted_by == "root_event:task-trail-001"
    assert records[1].delegation_ref == "delegate-reviewer"
    assert records[2].parent_cause == "event-plan"
    assert records[3].approval_ref == "approval-human-001"
    assert records[3].evidence_refs == ("evidence-review-001",)
    assert records[3].high_impact is True
    assert records[3].to_cml_dict()["actor"] == {
        "pid": 0,
        "uid": 0,
        "comm": "runtime:ls",
    }


def test_valid_recursive_lineage_allows_authorization_and_validates_schema() -> None:
    report = _audit_fixture("valid_recursive.json")

    assert report.passed is True
    assert report.authorization_allowed is True
    assert report.root_ids == ("task-recursive-001",)
    assert set(report.blocking_codes) == set()
    assert require_valid_causal_ancestry(report) is report
    assert _schema_errors(REPORT_SCHEMA, report.to_dict()) == []


def test_missing_parent_blocks_downstream_authorization() -> None:
    report = _audit_fixture("missing_parent.json")

    assert report.passed is False
    assert report.authorization_allowed is False
    assert "CML-AUDIT-R1-MISSING_PARENT" in report.blocking_codes
    assert "LS-CML-R6-ORPHAN_HIGH_IMPACT_ACTION" in report.blocking_codes
    with pytest.raises(CausalAuthorizationBlocked, match="MISSING_PARENT"):
        require_valid_causal_ancestry(report)


def test_ambiguous_root_is_reviewable_but_blocks_authorization() -> None:
    report = _audit_fixture("ambiguous_root.json")

    assert "CML-AUDIT-R4-AMBIGUOUS_ROOT" in report.blocking_codes
    assert report.authorization_allowed is False
    with pytest.raises(CausalAuthorizationBlocked):
        require_valid_causal_ancestry(report)


def test_broken_recursive_lineage_detects_cycle() -> None:
    report = _audit_fixture("broken_lineage.json")

    assert report.passed is False
    assert report.authorization_allowed is False
    assert "LS-CML-R5-BROKEN_LINEAGE" in report.blocking_codes


def test_causal_report_becomes_trail_event_and_artifact_extension() -> None:
    report = _audit_fixture("missing_parent.json")
    event = causal_audit_event(report, parent_cause="event-route")
    artifact = ReusableArtifact(
        artifact_id="artifact-001",
        task_id=report.task_id,
        trail_id=report.trail_id,
        created_at=CREATED_AT,
        route_refs=("route-001",),
        evidence_refs=("evidence-001",),
        contribution_refs=("contribution-001",),
        decision_ref="decision-001",
        execution_ref=None,
        replay_ref=None,
    )
    payload = attach_causal_audit(artifact, [report])

    assert event.event_type is TrailEventType.CAUSAL_AUDIT
    assert event.payload["authorization_allowed"] is False
    assert payload["causal_audit_refs"] == [report.audit_id]
    assert any(
        item["code"] == "CML-AUDIT-R1-MISSING_PARENT"
        for item in payload["causal_findings"]
    )
    assert _schema_errors(ARTIFACT_SCHEMA, payload) == []


def test_cml_is_disabled_by_default() -> None:
    with pytest.raises(CausalAuditDisabledError):
        CMLCausalAuditAdapter().audit(_valid_trail())


def test_cml_injected_runner_preserves_findings_and_summary() -> None:
    captured = []

    def runner(records, config):
        captured.extend(record.to_cml_dict() for record in records)
        return {
            "summary": {
                "total": len(records),
                "ok": len(records),
                "warn": 0,
                "fail": 0,
                "passed": True,
            },
            "findings": [
                {
                    "code": "OK",
                    "severity": "OK",
                    "record_id": record.record_id,
                    "message": "All rules passed",
                }
                for record in records
            ],
        }

    adapter = CMLCausalAuditAdapter(
        CMLConfig(enabled=True),
        runner=runner,
    )
    report = adapter.audit(_valid_trail())

    assert report.adapter == "cml"
    assert report.authorization_allowed is True
    assert report.metadata["transport"] == "injected"
    assert captured[0]["permitted_by"] == "root_event:task-trail-001"
    assert _schema_errors(REPORT_SCHEMA, report.to_dict()) == []


def test_cml_timeout_is_normalized() -> None:
    def runner(records, config):
        raise TimeoutError

    adapter = CMLCausalAuditAdapter(
        CMLConfig(enabled=True),
        runner=runner,
    )
    with pytest.raises(CausalAuditTimeoutError):
        adapter.audit(_valid_trail())


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"summary": {}, "findings": "not-a-list"},
        {
            "summary": {},
            "findings": [
                {
                    "code": "OK",
                    "severity": "UNKNOWN",
                    "record_id": "record-1",
                    "message": "bad severity",
                }
            ],
        },
    ],
)
def test_malformed_cml_responses_fail_closed(response: dict) -> None:
    def runner(records, config):
        return response

    adapter = CMLCausalAuditAdapter(
        CMLConfig(enabled=True),
        runner=runner,
    )
    with pytest.raises(MalformedCausalAuditResponseError):
        adapter.audit(_valid_trail())
