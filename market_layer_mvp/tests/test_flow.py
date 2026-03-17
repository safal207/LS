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


def test_full_market_layer_flow_with_all_steps(tmp_path: Path) -> None:
    client = _client_with_tmp_db(tmp_path)

    # governance and treasury setup
    governance = client.get("/governance")
    assert governance.status_code == 200
    assert any(x["key"] == "holdback_days" for x in governance.json())

    update_holdback_days = client.post("/governance/holdback_days", json={"value": 0})
    assert update_holdback_days.status_code == 200

    project_resp = client.post(
        "/projects",
        json={"name": "proj-mvp", "treasury_balance": 500},
    )
    assert project_resp.status_code == 200
    project_id = project_resp.json()["id"]

    # agents and task
    agent_a = client.post("/agents", json={"name": "agent-a"}).json()["id"]
    agent_b = client.post("/agents", json={"name": "agent-b"}).json()["id"]

    task_resp = client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "title": "Build endpoint",
            "description": "API",
            "reward": 100,
        },
    )
    assert task_resp.status_code == 200
    task = task_resp.json()
    task_id = task["id"]
    assert task["escrow_locked"] == 100

    # bids + auction scoring
    assert (
        client.post(
            f"/tasks/{task_id}/bids",
            json={"agent_id": agent_a, "price": 80, "eta_hours": 48},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/tasks/{task_id}/bids",
            json={"agent_id": agent_b, "price": 70, "eta_hours": 24},
        ).status_code
        == 200
    )

    assign_best = client.post(f"/tasks/{task_id}/assign/best")
    assert assign_best.status_code == 200
    assigned_agent_id = assign_best.json()["assigned_agent_id"]
    assert assigned_agent_id in [agent_a, agent_b]

    # delivery + verification v2 stages
    deliver_resp = client.post(
        f"/tasks/{task_id}/deliver",
        json={
            "task_id": task_id,
            "agent_id": assigned_agent_id,
            "hash": "deadbeef12345678",
            "quality_score": 0.91,
        },
    )
    assert deliver_resp.status_code == 200

    auto_stage = client.post(
        f"/tasks/{task_id}/verify/stage",
        json={"stage": "auto", "passed": True, "note": "schema ok"},
    )
    assert auto_stage.status_code == 200

    reviewer_stage = client.post(
        f"/tasks/{task_id}/verify/stage",
        json={"stage": "reviewer", "passed": True, "note": "peer approved"},
    )
    assert reviewer_stage.status_code == 200
    assert reviewer_stage.json()["status"] == "verified"

    impact_stage = client.post(
        f"/tasks/{task_id}/verify/stage",
        json={"stage": "impact", "passed": True, "note": "impact tracked", "impact_score": 0.8},
    )
    assert impact_stage.status_code == 200
    assert impact_stage.json()["impact_score"] == 0.8

    # accept + scheduled settlement + settlement run
    settlement_resp = client.post(f"/tasks/{task_id}/accept")
    assert settlement_resp.status_code == 200
    assert settlement_resp.json()["paid_now"] == 80.0
    assert settlement_resp.json()["holdback_left"] == 20.0

    settlements = client.get("/settlements")
    assert settlements.status_code == 200
    assert len(settlements.json()) == 1
    assert settlements.json()[0]["status"] == "pending"

    run_resp = client.post("/settlement/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["released_count"] == 1
    assert run_resp.json()["released_amount"] == 20.0

    # ledger observability
    ledger_resp = client.get("/ledger")
    assert ledger_resp.status_code == 200
    event_types = [evt["event_type"] for evt in ledger_resp.json()]
    for expected in [
        "treasury_updated",
        "bid_submitted",
        "verification_stage_recorded",
        "settlement_scheduled",
        "settlement_released",
        "governance_updated",
    ]:
        assert expected in event_types

    app.dependency_overrides.clear()


def test_dispute_penalty_flow(tmp_path: Path) -> None:
    client = _client_with_tmp_db(tmp_path)

    project_id = client.post(
        "/projects",
        json={"name": "proj-dispute", "treasury_balance": 200},
    ).json()["id"]
    agent_id = client.post("/agents", json={"name": "agent-dispute"}).json()["id"]

    task_id = client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "title": "Risk model",
            "description": "deliver",
            "reward": 50,
        },
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

    agents_resp = client.get("/agents")
    penalized_agent = [a for a in agents_resp.json() if a["id"] == agent_id][0]
    assert penalized_agent["reputation"] < 1.0

    app.dependency_overrides.clear()
