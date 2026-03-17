import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import Base
from db.database import get_db


def test_market_layer_end_to_end_flow(tmp_path: Path) -> None:
    db_path = tmp_path / "test_market_layer.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    agent_resp = client.post("/agents", json={"name": "agent-test"})
    assert agent_resp.status_code == 200
    agent_id = agent_resp.json()["id"]

    task_resp = client.post(
        "/tasks",
        json={"title": "Build endpoint", "description": "API", "reward": 100},
    )
    assert task_resp.status_code == 200
    task = task_resp.json()
    task_id = task["id"]
    assert task["escrow_locked"] == 100

    assign_resp = client.post(f"/tasks/{task_id}/assign", json={"agent_id": agent_id})
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "assigned"

    deliver_resp = client.post(
        f"/tasks/{task_id}/deliver",
        json={
            "task_id": task_id,
            "agent_id": agent_id,
            "hash": "deadbeef12345678",
            "quality_score": 0.9,
        },
    )
    assert deliver_resp.status_code == 200

    verify_resp = client.post(f"/tasks/{task_id}/verify", json={"approved": True})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "verified"

    settlement_resp = client.post(f"/tasks/{task_id}/accept")
    assert settlement_resp.status_code == 200
    settlement = settlement_resp.json()
    assert settlement["paid_now"] == 80.0
    assert settlement["holdback_left"] == 20.0

    ledger_resp = client.get("/ledger")
    assert ledger_resp.status_code == 200
    event_types = [evt["event_type"] for evt in ledger_resp.json()]
    assert "task_created" in event_types
    assert "payout_released" in event_types

    app.dependency_overrides.clear()
