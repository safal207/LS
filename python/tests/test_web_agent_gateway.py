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
    assert payload["personal_cognitive_garden_update"] is None
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
    assert response.json()["personal_cognitive_garden_update"] is None


def test_web_gateway_proposes_personal_cognitive_garden_update(tmp_path):
    app = create_app(artifact_dir=tmp_path / "council-ledger", enable_cors=False)
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        json={
            "prompt": "Review this strategy session for human development and skill growth.",
            "raw_output": (
                "The session improves product framing and creates a practice loop for "
                "turning AI conversations into a Personal Cognitive Garden update."
            ),
            "agent_id": "pcg-test-agent",
            "agent_type": "external",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action_evidence_gate"]["decision"] == "allow"
    update = payload["personal_cognitive_garden_update"]
    assert update["schema_version"] == "personal-cognitive-garden-update.v0.1"
    assert update["status"] == "proposed"
    assert update["requires_human_review"] is True
    assert update["governance"]["durable_state_allowed"] is False
    assert update["governance"]["external_action_allowed"] is False
    assert update["governance"]["sharing_scope"] == "private"
    assert update["development_effect"]["is_developmental"] is True
    assert "development_signal_extraction" in update["development_effect"]["human_skill_delta"]


def test_web_gateway_accepts_personal_cognitive_garden_update(tmp_path):
    app = create_app(artifact_dir=tmp_path / "council-ledger", enable_cors=False)
    client = TestClient(app)

    route_response = client.post(
        "/v1/chat",
        json={
            "prompt": "Проверь эту сессию на развитие навыков и направление роста.",
            "raw_output": "Каждая сессия Codex должна превращаться в навык, артефакт или направление роста.",
            "agent_id": "pcg-test-agent",
            "agent_type": "external",
        },
    )
    proposal = route_response.json()["personal_cognitive_garden_update"]

    accept_response = client.post(
        "/v1/pcg/accept",
        json={
            "proposal": proposal,
            "reviewer": "operator",
            "review_note": "Accepted as a working principle for Codex sessions.",
        },
    )

    assert accept_response.status_code == 200
    accepted = accept_response.json()
    assert accepted["accepted"] is True
    assert accepted["garden_update_id"] == proposal["garden_update_id"]
    assert accepted["accepted_node"]["status"] == "accepted"
    assert accepted["accepted_node"]["requires_human_review"] is False
    assert accepted["accepted_node"]["governance"]["durable_state_allowed"] is True
    assert accepted["accepted_node"]["governance"]["external_action_allowed"] is False
    assert accepted["accepted_node"]["governance"]["sharing_scope"] == "private"
    assert list((tmp_path / "personal-cognitive-garden").glob("*.accepted.json"))


def test_web_gateway_rejects_non_proposed_garden_acceptance(tmp_path):
    app = create_app(artifact_dir=tmp_path / "council-ledger", enable_cors=False)
    client = TestClient(app)

    response = client.post(
        "/v1/pcg/accept",
        json={
            "proposal": {
                "garden_update_id": "pcg_update_bad",
                "status": "accepted",
                "requires_human_review": False,
            }
        },
    )

    assert response.status_code == 400
