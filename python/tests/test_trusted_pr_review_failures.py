"""Trusted PR Review fail-closed tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from modules.trusted_runtime.causal import CausalRecord, DeterministicCausalAuditAdapter
from modules.trusted_runtime.contracts import DecisionCode
from modules.trusted_runtime.evidence import evidence_decision_event
from modules.trusted_runtime.execution import ExecutionState
from modules.trusted_runtime.pr_review_analysis import analyze_diff
from modules.trusted_runtime.pr_review_mvp import (
    _audit_trail,
    _authorize_and_execute,
    _decide,
)
from modules.trusted_runtime.pr_review_plan import plan_pr_review


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/pr-review"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _diff(name: str) -> str:
    return (FIXTURES / f"{name}.diff").read_text(encoding="utf-8")


def test_broken_causal_fixture_blocks_protected_action() -> None:
    fixture = _load("broken_causal.json")
    records = tuple(CausalRecord.from_mapping(item) for item in fixture["records"])
    report = DeterministicCausalAuditAdapter().audit_records(
        records,
        task_id=fixture["task_id"],
        trail_id=fixture["trail_id"],
        actor="adapter:test",
        created_at="2026-06-23T14:00:00Z",
    )

    assert report.authorization_allowed is False
    assert set(fixture["expected_codes"]).issubset(set(report.blocking_codes))


def test_expired_allow_authorization_never_writes_effect(tmp_path: Path) -> None:
    fixture = _load("expired_authorization.json")
    analysis = analyze_diff(_diff("allow"))
    planned = plan_pr_review(
        analysis,
        scenario="allow",
        created_at=fixture["issued_at"],
    )
    trail, audit, audit_event_id = _audit_trail(planned)
    decision, decision_event_id = _decide(
        trail,
        audit,
        audit_event_id,
        analysis,
        scenario="allow",
    )
    assert decision.decision is DecisionCode.ALLOW
    trail = replace(trail, events=(*trail.events, evidence_decision_event(decision)))

    _, execution, _ = _authorize_and_execute(
        trail,
        decision,
        audit_event_id,
        decision_event_id,
        analysis,
        planned,
        tmp_path,
        expires_at=fixture["expires_at"],
    )

    assert execution.state.value == fixture["expected_state"]
    assert execution.decision_code.value == fixture["expected_decision_code"]
    assert execution.state is ExecutionState.REJECTED
    assert execution.effect_attempted is False
    effect_files = list((tmp_path / "protected").glob("*.review.json"))
    assert len(effect_files) == fixture["expected_effect_files"]
