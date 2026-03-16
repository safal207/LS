from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, build_session_factory, get_db
from .models import Agent, Project, Task, TaskStatus
from .schemas import (
    AcceptTaskIn,
    AgentCreate,
    AgentOut,
    CompleteTaskIn,
    CreationEventOut,
    ProjectCreate,
    ProjectOut,
    RewardComputeOut,
    TaskCreate,
    TaskOut,
)
from .services import accept_task, complete_task, process_vested_payouts


def create_app(database_url: str = "sqlite:///./market_layer.db") -> FastAPI:
    app = FastAPI(title="Market Layer MVP")
    engine, session_factory = build_session_factory(database_url)
    Base.metadata.create_all(bind=engine)

    def db_dep() -> Generator[Session, None, None]:
        yield from get_db(session_factory)

    @app.post("/agents", response_model=AgentOut)
    def create_agent(payload: AgentCreate, db: Session = Depends(db_dep)) -> Agent:
        if db.scalar(select(Agent).where(Agent.name == payload.name)):
            raise HTTPException(status_code=400, detail="Agent name already exists")
        agent = Agent(name=payload.name)
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent

    @app.get("/agents/{agent_id}", response_model=AgentOut)
    def get_agent(agent_id: int, db: Session = Depends(db_dep)) -> Agent:
        agent = db.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent

    @app.post("/projects", response_model=ProjectOut)
    def create_project(payload: ProjectCreate, db: Session = Depends(db_dep)) -> Project:
        project = Project(name=payload.name, treasury=payload.treasury)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @app.post("/tasks", response_model=TaskOut)
    def create_task(payload: TaskCreate, db: Session = Depends(db_dep)) -> Task:
        project = db.get(Project, payload.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.treasury < payload.reward_budget:
            raise HTTPException(status_code=400, detail="reward_budget exceeds treasury")
        task = Task(
            project_id=payload.project_id,
            title=payload.title,
            description=payload.description,
            reward_budget=payload.reward_budget,
            status=TaskStatus.OPEN,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @app.get("/tasks/open", response_model=list[TaskOut])
    def list_open_tasks(db: Session = Depends(db_dep)) -> list[Task]:
        return db.scalars(select(Task).where(Task.status == TaskStatus.OPEN)).all()

    @app.post("/tasks/{task_id}/accept", response_model=dict)
    def accept(task_id: int, payload: AcceptTaskIn, db: Session = Depends(db_dep)) -> dict:
        assignment = accept_task(db, task_id=task_id, agent_id=payload.agent_id)
        return {
            "assignment_id": assignment.id,
            "task_id": assignment.task_id,
            "agent_id": assignment.agent_id,
            "status": assignment.status,
        }

    @app.post("/tasks/{task_id}/complete", response_model=CreationEventOut)
    def complete(task_id: int, payload: CompleteTaskIn, db: Session = Depends(db_dep)):
        return complete_task(
            db,
            task_id=task_id,
            agent_id=payload.agent_id,
            artifact=payload.artifact,
            impact_score=payload.impact_score,
            quality_score=payload.quality_score,
        )

    @app.post("/rewards/compute", response_model=RewardComputeOut)
    def compute_rewards(db: Session = Depends(db_dep)) -> RewardComputeOut:
        processed_count, total_amount = process_vested_payouts(db)
        return RewardComputeOut(processed_count=processed_count, total_amount=total_amount)

    return app


app = create_app()
