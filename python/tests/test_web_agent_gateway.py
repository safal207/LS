from __future__ import annotations

from fastapi.testclient import TestClient

from ls.agent_shell.web_gateway import create_app


def test_web_gateway_health(tmp_path):
    app = create_app(artifact_dir=tmp_path / "council-ledger", enable_cors=False)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_web_gateway_routes_agent_output(tmp_path):
    app = create_app(artifact_dir=tmp_path / "council-ledger", enable_cors=False)
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        json={
            "prompt": "Explain what LS does.",
            "raw_output": "LS checks agent output before showing it.",
            "agent_id": "kimi-test",
            "agent_type": "kimi",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == "kimi-test"
    assert payload["agent_type"] == "kimi"
    assert payload["raw_agent_output"] == "LS checks agent output before showing it."
    assert payload["final_output"]
    assert payload["action_evidence_gate"]["decision"] == "allow"
    assert list((tmp_path / "council-ledger").glob("*.json"))


def test_web_gateway_holds_high_risk_agent_action(tmp_path):
    app = create_app(artifact_dir=tmp_path / "council-ledger", enable_cors=False)
    client = TestClient(app)

    response = client.post(
        "/v1/agent-gateway",
        json={
            "prompt": "Push was rejected. What should we do?",
            "raw_output": "Force push local main to origin/main.",
            "agent_id": "claude-test",
            "agent_type": "claude",
            "metadata": {
                "action_type": "repo_push",
                "target": "main",
                "risk_level": "high",
                "production": True,
                "destructive": True,
            },
        },
    )

    assert response.status_code == 200
    gate = response.json()["action_evidence_gate"]
    assert gate["decision"] == "hold"
    assert gate["stop_reason"] == "missing_operator_confirmation"
