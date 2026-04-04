from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.market_layer.database import build_session_factory
from apps.market_layer.main import create_app
from apps.market_layer.models import RewardPayout


def test_market_flow_end_to_end(tmp_path):
    db_path = tmp_path / "market.db"
    app = create_app(database_url=f"sqlite:///{db_path}")
    client = TestClient(app)

    agent = client.post("/agents", json={"name": "agent-1"}).json()
    project = client.post("/projects", json={"name": "project-a", "treasury": 1000}).json()

    task = client.post(
        "/tasks",
        json={
            "project_id": project["id"],
            "title": "Build parser",
            "description": "Return artifact",
            "reward_budget": 100,
        },
    ).json()
    assert task["escrow_balance"] == 100.0

    project_after_task = client.get(f"/projects/{project['id']}").json()
    assert project_after_task["treasury"] == 900.0

    open_tasks = client.get("/tasks/open").json()
    assert len(open_tasks) == 1
    assert open_tasks[0]["id"] == task["id"]

    accepted = client.post(f"/tasks/{task['id']}/accept", json={"agent_id": agent["id"]})
    assert accepted.status_code == 200

    complete = client.post(
        f"/tasks/{task['id']}/complete",
        json={
            "agent_id": agent["id"],
            "artifact": "commit:abc123",
            "impact_score": 0.8,
            "quality_score": 0.5,
        },
    )
    assert complete.status_code == 200

    agent_after = client.get(f"/agents/{agent['id']}").json()
    assert agent_after["reputation_score"] == 0.4
    assert agent_after["balance"] == 8.0

    engine, factory = build_session_factory(f"sqlite:///{db_path}")
    with factory() as db:
        delayed = db.scalar(select(RewardPayout).where(RewardPayout.vested.is_(False)))
        assert delayed is not None
        delayed.available_at = datetime.utcnow() - timedelta(days=1)
        db.commit()

    rewards = client.post("/rewards/compute")
    assert rewards.status_code == 200
    assert rewards.json()["processed_count"] == 1

    agent_final = client.get(f"/agents/{agent['id']}").json()
    assert agent_final["balance"] == 40.0


def test_treasury_is_reserved_on_task_creation(tmp_path):
    db_path = tmp_path / "market2.db"
    app = create_app(database_url=f"sqlite:///{db_path}")
    client = TestClient(app)

    project = client.post("/projects", json={"name": "project-b", "treasury": 50}).json()

    first = client.post(
        "/tasks",
        json={
            "project_id": project["id"],
            "title": "T1",
            "description": "D1",
            "reward_budget": 30,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/tasks",
        json={
            "project_id": project["id"],
            "title": "T2",
            "description": "D2",
            "reward_budget": 30,
        },
    )
    assert second.status_code == 400


def test_economic_efficiency_endpoint(tmp_path):
    db_path = tmp_path / "market3.db"
    app = create_app(database_url=f"sqlite:///{db_path}")
    client = TestClient(app)

    response = client.post(
        "/analytics/efficiency",
        json={
            "tasks_per_month": 200,
            "avg_reward_budget": 100,
            "avg_impact_score": 0.8,
            "avg_quality_score": 0.75,
            "baseline_human_cost_per_task": 120,
            "automation_uplift_pct": 0.15,
            "platform_opex_monthly": 5000,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert round(data["payout_per_task"], 2) == 60.0
    assert round(data["net_saving_per_task"], 2) == 60.0
    assert round(data["gross_monthly_saving"], 2) == 12000.0
    assert round(data["automation_uplift_value"], 2) == 1800.0
    assert round(data["monthly_net_effect"], 2) == 8800.0
