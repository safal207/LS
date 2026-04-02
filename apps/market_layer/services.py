from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Agent,
    AssignmentStatus,
    CreationEvent,
    RewardPayout,
    Task,
    TaskAssignment,
    TaskStatus,
)

IMPACT_THRESHOLD = 0.1
IMMEDIATE_FRACTION = 0.2
VESTING_DELAY_DAYS = 7


def compute_payout(task: Task, impact_score: float, quality_score: float) -> float:
    return task.reward_budget * impact_score * quality_score


def _must_get(model, db: Session, record_id: int):
    obj = db.get(model, record_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {record_id} not found")
    return obj


def accept_task(db: Session, task_id: int, agent_id: int) -> TaskAssignment:
    task = _must_get(Task, db, task_id)
    _must_get(Agent, db, agent_id)
    if task.status != TaskStatus.OPEN:
        raise HTTPException(status_code=400, detail="Task is not open")

    existing = db.scalar(select(TaskAssignment).where(TaskAssignment.task_id == task_id))
    if existing:
        raise HTTPException(status_code=400, detail="Task already assigned")

    assignment = TaskAssignment(task_id=task_id, agent_id=agent_id, status=AssignmentStatus.ACCEPTED)
    task.status = TaskStatus.IN_PROGRESS
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def complete_task(
    db: Session,
    task_id: int,
    agent_id: int,
    artifact: str,
    impact_score: float,
    quality_score: float,
) -> CreationEvent:
    task = _must_get(Task, db, task_id)
    agent = _must_get(Agent, db, agent_id)

    assignment = db.scalar(
        select(TaskAssignment).where(TaskAssignment.task_id == task_id, TaskAssignment.agent_id == agent_id)
    )
    if not assignment:
        raise HTTPException(status_code=400, detail="Task is not assigned to this agent")
    if task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Task is not in progress")
    if impact_score < IMPACT_THRESHOLD:
        raise HTTPException(status_code=400, detail=f"impact_score must be >= {IMPACT_THRESHOLD}")

    event = CreationEvent(
        task_id=task_id,
        agent_id=agent_id,
        impact_score=impact_score,
        quality_score=quality_score,
        artifact=artifact,
    )
    payout_total = compute_payout(task, impact_score, quality_score)
    immediate_amount = payout_total * IMMEDIATE_FRACTION
    delayed_amount = payout_total - immediate_amount

    if payout_total > task.escrow_balance:
        raise HTTPException(status_code=400, detail="Computed payout exceeds task escrow")

    now = datetime.utcnow()
    payouts = [
        RewardPayout(
            agent_id=agent_id,
            task_id=task_id,
            amount=immediate_amount,
            vested=True,
            available_at=now,
        ),
        RewardPayout(
            agent_id=agent_id,
            task_id=task_id,
            amount=delayed_amount,
            vested=False,
            available_at=now + timedelta(days=VESTING_DELAY_DAYS),
        ),
    ]

    assignment.status = AssignmentStatus.COMPLETED
    assignment.artifact = artifact
    task.status = TaskStatus.COMPLETED

    agent.reputation_score += impact_score * quality_score
    agent.balance += immediate_amount
    task.escrow_balance -= immediate_amount

    db.add(event)
    for payout in payouts:
        db.add(payout)

    db.commit()
    db.refresh(event)
    return event


def process_vested_payouts(db: Session) -> tuple[int, float]:
    now = datetime.utcnow()
    rows = db.scalars(
        select(RewardPayout).where(RewardPayout.vested.is_(False), RewardPayout.available_at <= now)
    ).all()

    total = 0.0
    processed = 0
    for payout in rows:
        agent = _must_get(Agent, db, payout.agent_id)
        task = _must_get(Task, db, payout.task_id)
        if task.escrow_balance < payout.amount:
            continue
        task.escrow_balance -= payout.amount
        agent.balance += payout.amount
        payout.vested = True
        total += payout.amount
        processed += 1

    db.commit()
    return processed, total
