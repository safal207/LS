from fastapi.testclient import TestClient

import app.main as main
from app.store import ApprovalStore


client = TestClient(main.app)


def test_healthz_smoke():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ls-qwen-autopilot-agent"}


def test_evaluate_reports_completed_qwen_assessment(monkeypatch, tmp_path):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr(
        main.QwenRiskReasoner,
        "assess",
        lambda self, payload, policy: {
            "risk_level": "LOW",
            "decision": "ALLOW",
            "confidence": 0.94,
            "reasons": ["Read-only internal action"],
            "required_controls": [],
        },
    )
    monkeypatch.setattr(main, "store", ApprovalStore(str(tmp_path / "approvals.db")))

    response = client.post(
        "/api/evaluate",
        json={
            "actor": "reporting-agent",
            "action": "Generate read-only weekly report",
            "resource": "analytics warehouse",
            "context": "Internal use",
            "requested_effect": "Create a draft report",
            "metadata": {"reversible": True, "has_test_evidence": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["qwen"]["status"] == "COMPLETED"
    assert body["execution"] == {"status": "NOT_EXECUTED", "authority": "advisory_only"}


def test_missing_qwen_credentials_fail_closed(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setattr(main, "store", ApprovalStore(str(tmp_path / "approvals.db")))

    response = client.post(
        "/api/evaluate",
        json={
            "actor": "ops-agent",
            "action": "Send email to customer",
            "metadata": {"reversible": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "HUMAN_APPROVAL"
    assert body["qwen"]["status"] == "NOT_RUN"
    assert body["approval_id"]


def test_approval_resolution_is_explicit_and_idempotent(tmp_path):
    store = ApprovalStore(str(tmp_path / "approvals.db"))
    approval_id = store.create({"action": "Send email"}, {"decision": "HUMAN_APPROVAL"})

    first = store.resolve(approval_id, "APPROVE", "alexey", "Reviewed")
    second = store.resolve(approval_id, "REJECT", "another-reviewer", "Too late")

    assert first is not None
    assert first["status"] == "APPROVED"
    assert first["resolution_applied"] is True
    assert second is not None
    assert second["status"] == "APPROVED"
    assert second["resolution_applied"] is False
