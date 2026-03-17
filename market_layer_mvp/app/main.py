from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.models import Base
from db.database import SessionLocal, engine, get_db

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = SessionLocal()
    try:
        crud.ensure_governance_defaults(db)
        yield
    finally:
        db.close()


app = FastAPI(title="Market Layer MVP", version="1.0.0", lifespan=lifespan)


@app.post("/agents", response_model=schemas.AgentOut)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    return crud.create_agent(db, name=agent.name)


@app.get("/agents", response_model=list[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return crud.list_agents(db)


@app.post("/projects", response_model=schemas.ProjectOut)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    return crud.create_project(db, name=project.name, treasury_balance=project.treasury_balance)


@app.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return crud.list_projects(db)


@app.post("/tasks", response_model=schemas.TaskOut)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_task(
            db,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            reward=task.reward,
            use_case=task.use_case,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return crud.list_tasks(db)


@app.post("/tasks/{task_id}/bids", response_model=schemas.BidOut)
def submit_bid(task_id: int, bid: schemas.BidCreate, db: Session = Depends(get_db)):
    try:
        return crud.submit_bid(
            db,
            task_id=task_id,
            agent_id=bid.agent_id,
            price=bid.price,
            eta_hours=bid.eta_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/tasks/{task_id}/bids", response_model=list[schemas.BidOut])
def list_bids(task_id: int, db: Session = Depends(get_db)):
    return crud.list_task_bids(db, task_id=task_id)


@app.post("/tasks/{task_id}/assign", response_model=schemas.TaskOut)
def assign_task(task_id: int, payload: schemas.AssignTaskRequest, db: Session = Depends(get_db)):
    try:
        return crud.assign_task(db, task_id=task_id, agent_id=payload.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/assign/best", response_model=schemas.TaskOut)
def assign_best_bid(task_id: int, db: Session = Depends(get_db)):
    try:
        return crud.assign_best_bid(db, task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/deliver", response_model=schemas.ArtifactOut)
def submit_artifact(
    task_id: int, artifact: schemas.ArtifactSubmit, db: Session = Depends(get_db)
):
    if artifact.task_id != task_id:
        raise HTTPException(status_code=400, detail="task_id mismatch")
    try:
        return crud.submit_artifact(
            db,
            task_id=task_id,
            agent_id=artifact.agent_id,
            hash_value=artifact.hash,
            quality_score=artifact.quality_score,
            content=artifact.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc




@app.post("/tasks/{task_id}/execute", response_model=schemas.ArtifactOut)
def execute_task(task_id: int, db: Session = Depends(get_db)):
    try:
        return crud.execute_task(db, task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/autoloop", response_model=schemas.TaskOut)
def auto_loop_task(task_id: int, db: Session = Depends(get_db)):
    try:
        return crud.auto_loop_task(db, task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/tasks/{task_id}/verify/stage", response_model=schemas.TaskOut)
def verify_stage(
    task_id: int,
    payload: schemas.VerifyStageRequest,
    db: Session = Depends(get_db),
):
    try:
        return crud.verify_stage(
            db,
            task_id=task_id,
            stage=payload.stage,
            passed=payload.passed,
            note=payload.note,
            impact_score=payload.impact_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/verify", response_model=schemas.TaskOut)
def verify_task(
    task_id: int,
    payload: schemas.VerifyTaskRequest,
    db: Session = Depends(get_db),
):
    try:
        return crud.verify_task(db, task_id=task_id, approved=payload.approved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/dispute", response_model=schemas.TaskOut)
def dispute_task(
    task_id: int,
    payload: schemas.DisputeTaskRequest,
    db: Session = Depends(get_db),
):
    try:
        return crud.dispute_task(db, task_id=task_id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tasks/{task_id}/accept", response_model=schemas.SettlementResult)
def accept_task(task_id: int, db: Session = Depends(get_db)):
    try:
        task, paid_now, holdback_left = crud.accept_task(db, task_id=task_id)
        return schemas.SettlementResult(
            task_id=task.id,
            paid_now=paid_now,
            holdback_left=holdback_left,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/settlements", response_model=list[schemas.SettlementOut])
def list_settlements(db: Session = Depends(get_db)):
    return crud.list_settlements(db)


@app.post("/settlement/run", response_model=schemas.SettlementRunResult)
def run_settlement(db: Session = Depends(get_db)):
    released_count, released_amount = crud.run_settlement(db)
    return schemas.SettlementRunResult(
        released_count=released_count,
        released_amount=released_amount,
    )


@app.get("/governance", response_model=list[schemas.GovernanceParamOut])
def list_governance(db: Session = Depends(get_db)):
    return crud.list_governance(db)


@app.post("/governance/{key}", response_model=schemas.GovernanceParamOut)
def update_governance(
    key: str,
    payload: schemas.GovernanceUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return crud.update_governance(db, key=key, value=payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/ledger", response_model=list[schemas.LedgerEventOut])
def list_ledger(db: Session = Depends(get_db)):
    return crud.list_events(db)
