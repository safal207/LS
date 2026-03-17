import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app
from app.models import Base
from db.database import get_db


def _client_with_tmp_db(tmp_path: Path) -> TestClient:
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
    return TestClient(app)


def test_market_layer_end_to_end_flow_with_bids(tmp_path: Path) -> None:
    client = _client_with_tmp_db(tmp_path)

    agent_a = client.post("/agents", json={"name": "agent-a"}).json()["id"]
    agent_b = client.post("/agents", json={"name": "agent-b"}).json()["id"]

    task_resp = client.post(
        "/tasks",
        json={"title": "Build endpoint", "description": "API", "reward": 100},
    )
    assert task_resp.status_code == 200
    task = task_resp.json()
    task_id = task["id"]
    assert task["escrow_locked"] == 100

    bid_1 = client.post(f"/tasks/{task_id}/bids", json={"agent_id": agent_a, "price": 90})
    bid_2 = client.post(f"/tasks/{task_id}/bids", json={"agent_id": agent_b, "price": 80})
    assert bid_1.status_code == 200
    assert bid_2.status_code == 200

    bids_resp = client.get(f"/tasks/{task_id}/bids")
    assert bids_resp.status_code == 200
    assert len(bids_resp.json()) == 2

    assign_resp = client.post(f"/tasks/{task_id}/assign", json={"agent_id": agent_b})
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "assigned"

    deliver_resp = client.post(
        f"/tasks/{task_id}/deliver",
        json={
            "task_id": task_id,
            "agent_id": agent_b,
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
    assert "bid_submitted" in event_types
    assert "payout_released" in event_types

    app.dependency_overrides.clear()


def test_dispute_flow_changes_status_and_writes_ledger(tmp_path: Path) -> None:
    client = _client_with_tmp_db(tmp_path)

    agent_id = client.post("/agents", json={"name": "agent-dispute"}).json()["id"]
    task_id = client.post(
        "/tasks",
        json={"title": "Risk model", "description": "deliver", "reward": 50},
    ).json()["id"]

    assert client.post(f"/tasks/{task_id}/assign", json={"agent_id": agent_id}).status_code == 200
    assert (
        client.post(
            f"/tasks/{task_id}/deliver",
            json={
                "task_id": task_id,
                "agent_id": agent_id,
                "hash": "cafebabe12345678",
                "quality_score": 0.2,
            },
        ).status_code
        == 200
    )

    dispute_resp = client.post(
        f"/tasks/{task_id}/dispute",
        json={"reason": "Auto-check failed during review"},
    )
    assert dispute_resp.status_code == 200
    assert dispute_resp.json()["status"] == "disputed"

    ledger_resp = client.get("/ledger")
    event_types = [evt["event_type"] for evt in ledger_resp.json()]
    assert "task_disputed" in event_types

    app.dependency_overrides.clear()
