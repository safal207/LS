import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import crud
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

    db = TestingSessionLocal()
    try:
        crud.ensure_governance_defaults(db)
    finally:
        db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_autoloop_landing_generator_closes_task(tmp_path: Path) -> None:
    client = _client_with_tmp_db(tmp_path)

    client.post("/governance/holdback_days", json={"value": 0})

    project_id = client.post(
        "/projects", json={"name": "proj-auto", "treasury_balance": 300}
    ).json()["id"]
    agent_a = client.post("/agents", json={"name": "agent-a"}).json()["id"]
    agent_b = client.post("/agents", json={"name": "agent-b"}).json()["id"]

    task_id = client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "title": "Landing for AI studio",
            "description": "Create conversion-focused landing page with CTA",
            "reward": 100,
            "use_case": "landing_generator",
        },
    ).json()["id"]

    assert (
        client.post(
            f"/tasks/{task_id}/bids", json={"agent_id": agent_a, "price": 80, "eta_hours": 24}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/tasks/{task_id}/bids", json={"agent_id": agent_b, "price": 70, "eta_hours": 48}
        ).status_code
        == 200
    )

    loop_resp = client.post(f"/tasks/{task_id}/autoloop")
    assert loop_resp.status_code == 200
    assert loop_resp.json()["status"] == "closed"

    ledger = client.get("/ledger").json()
    events = [x["event_type"] for x in ledger]
    assert "task_executed" in events
    assert "autoloop_completed" in events
    assert "settlement_released" in events

    app.dependency_overrides.clear()


def test_manual_execution_and_verification_v2(tmp_path: Path) -> None:
    client = _client_with_tmp_db(tmp_path)

    project_id = client.post(
        "/projects", json={"name": "proj-manual", "treasury_balance": 200}
    ).json()["id"]
    agent_id = client.post("/agents", json={"name": "agent-manual"}).json()["id"]

    task_id = client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "title": "Generic task",
            "description": "Build short output",
            "reward": 50,
            "use_case": "generic",
        },
    ).json()["id"]

    assert (
        client.post(
            f"/tasks/{task_id}/bids", json={"agent_id": agent_id, "price": 40, "eta_hours": 12}
        ).status_code
        == 200
    )
    assert client.post(f"/tasks/{task_id}/assign/best").status_code == 200

    exec_resp = client.post(f"/tasks/{task_id}/execute")
    assert exec_resp.status_code == 200
    assert "Result for task" in exec_resp.json()["content"]

    assert (
        client.post(
            f"/tasks/{task_id}/verify/stage",
            json={"stage": "auto", "passed": True, "note": "auto pass"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/tasks/{task_id}/verify/stage",
            json={"stage": "reviewer", "passed": True, "note": "review pass"},
        ).status_code
        == 200
    )
    impact = client.post(
        f"/tasks/{task_id}/verify/stage",
        json={"stage": "impact", "passed": True, "note": "impact", "impact_score": 0.6},
    )
    assert impact.status_code == 200
    assert impact.json()["status"] == "verified"

    app.dependency_overrides.clear()
