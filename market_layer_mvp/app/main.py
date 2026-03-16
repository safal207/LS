from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.models import Base
from db.database import engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Market Layer MVP", version="0.1.0")


@app.post("/agents", response_model=schemas.AgentOut)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    return crud.create_agent(db, name=agent.name)


@app.get("/agents", response_model=list[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return crud.list_agents(db)


@app.post("/tasks", response_model=schemas.TaskOut)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    return crud.create_task(
        db,
        title=task.title,
        description=task.description,
        reward=task.reward,
    )


@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return crud.list_tasks(db)


@app.post("/tasks/{task_id}/assign", response_model=schemas.TaskOut)
def assign_task(task_id: int, payload: schemas.AssignTaskRequest, db: Session = Depends(get_db)):
    try:
        return crud.assign_task(db, task_id=task_id, agent_id=payload.agent_id)
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


@app.get("/ledger", response_model=list[schemas.LedgerEventOut])
def list_ledger(db: Session = Depends(get_db)):
    return crud.list_events(db)
