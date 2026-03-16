from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

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

    # Force delayed payout to become due.
    session_factory = app.dependency_overrides or None
    assert session_factory is None  # sanity: using default DB wiring

    # Use direct SQLAlchemy session by re-creating app internals through endpoint side effects.
    # Updating available_at via API is out of scope for MVP tests.
    from apps.market_layer.database import build_session_factory

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
