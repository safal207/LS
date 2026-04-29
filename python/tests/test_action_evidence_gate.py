# -*- coding: utf-8 -*-
from __future__ import annotations

try:
    from agent.action_evidence_gate import ActionEvidenceGate, ActionEvidenceGateRequest
except ImportError:
    from modules.agent.action_evidence_gate import ActionEvidenceGate, ActionEvidenceGateRequest  # type: ignore[no-redef]


def test_action_evidence_gate_holds_profile_write_without_confirmation() -> None:
    gate = ActionEvidenceGate()
    result = gate.evaluate(
        ActionEvidenceGateRequest(
            action_type="profile_write",
            actor="profile-agent",
            target="operator_profile",
            requested_change={"preference": "short answers"},
            evidence={
                "operator_profile_write_decision": {
                    "decision": "requires_operator_confirmation",
                    "write_scope": "operator_profile",
                }
            },
        )
    )

    assert result.decision == "hold"
    assert result.stop_reason == "missing_operator_confirmation"
    assert "operator_confirmation" in result.required_evidence
    assert result.evidence_digest


def test_action_evidence_gate_allows_confirmed_profile_write() -> None:
    gate = ActionEvidenceGate()
    result = gate.evaluate(
        {
            "action_type": "profile_write",
            "actor": "profile-agent",
            "target": "operator_profile",
            "requested_change": {"preference": "short answers"},
            "evidence": {
                "operator_confirmed": True,
                "operator_profile_write_decision": {
                    "decision": "allow_profile_update",
                    "write_scope": "operator_profile",
                },
            },
        }
    )

    assert result.decision == "allow"
    assert result.stop_reason == "constraints_satisfied"


def test_action_evidence_gate_holds_memory_write_without_source() -> None:
    gate = ActionEvidenceGate()
    result = gate.evaluate(
        ActionEvidenceGateRequest(
            action_type="session_memory",
            actor="memory-agent",
            target="session_memory",
            requested_change="remember this preference",
            evidence={"operator_confirmed": True},
        )
    )

    assert result.decision == "hold"
    assert result.stop_reason == "missing_source_evidence"
    assert "source_evidence" in result.required_evidence


def test_action_evidence_gate_holds_memory_write_without_confirmation() -> None:
    gate = ActionEvidenceGate()
    result = gate.evaluate(
        ActionEvidenceGateRequest(
            action_type="session_memory",
            actor="memory-agent",
            target="session_memory",
            requested_change="remember this preference",
            evidence={
                "source_evidence": "operator said it in the current turn",
                "operator_profile_write_decision": {
                    "decision": "requires_operator_confirmation",
                    "requires_operator_confirmation": True,
                },
            },
        )
    )

    assert result.decision == "hold"
    assert result.stop_reason == "missing_operator_confirmation"
    assert "operator_confirmation" in result.required_evidence


def test_action_evidence_gate_rejects_high_risk_action_outside_scope() -> None:
    gate = ActionEvidenceGate()
    result = gate.evaluate(
        ActionEvidenceGateRequest(
            action_type="external_agent_action",
            actor="infra-agent",
            target="production-volume",
            requested_change={"operation": "delete"},
            evidence={"operator_confirmed": True, "risk_level": "high"},
        )
    )

    assert result.decision == "reject"
    assert result.stop_reason == "external_agent_scope_violation"
    assert "scope_authorization" in result.required_evidence


def test_action_evidence_gate_detects_tampered_artifact() -> None:
    gate = ActionEvidenceGate()
    result = gate.evaluate(
        ActionEvidenceGateRequest(
            action_type="agent_output",
            actor="status-agent",
            requested_change="Status is green.",
        )
    )
    artifact = dict(result.evidence_artifact)

    assert gate.verify_evidence_artifact(artifact).decision == "allow"

    tampered = dict(artifact)
    tampered["stop_reason"] = "constraints_changed_after_decision"
    verification = gate.verify_evidence_artifact(tampered)

    assert verification.decision == "reject"
    assert verification.stop_reason == "tampered_evidence"


def test_action_evidence_gate_checks_bitemporal_authorization() -> None:
    gate = ActionEvidenceGate()
    result = gate.evaluate(
        ActionEvidenceGateRequest(
            action_type="tool_call",
            actor="tool-agent",
            target="repo",
            requested_change={"operation": "push"},
            evidence={
                "operator_confirmed": True,
                "scope_authorized": True,
                "permission_record": {
                    "valid_from": "2026-04-29T09:00:00Z",
                    "valid_to": "2026-04-29T12:00:00Z",
                    "recorded_at": "2026-04-29T12:30:00Z",
                },
            },
            current_context={
                "action_time": "2026-04-29T10:00:00Z",
                "decision_time": "2026-04-29T10:05:00Z",
            },
        )
    )

    assert result.decision == "hold"
    assert result.stop_reason == "authorization_unknown_at_decision_time"
