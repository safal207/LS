from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import escrow, reputation
from .ledger import record_event
from .models import Agent, Artifact, Bid, BidStatus, EventType, Task, TaskStatus


def create_agent(db: Session, *, name: str) -> Agent:
    agent = Agent(name=name)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def list_agents(db: Session) -> list[Agent]:
    return list(db.scalars(select(Agent).order_by(Agent.id)).all())


def create_task(db: Session, *, title: str, description: str, reward: float) -> Task:
    task = Task(title=title, description=description, reward=reward)
    escrow.lock_reward(task)
    db.add(task)
    db.flush()
    record_event(
        db,
        EventType.task_created,
        task_id=task.id,
        payload={"title": title, "reward": reward},
    )
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session) -> list[Task]:
    return list(db.scalars(select(Task).order_by(Task.id.desc())).all())


def submit_bid(db: Session, *, task_id: int, agent_id: int, price: float) -> Bid:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status != TaskStatus.open:
        raise ValueError("Only open tasks accept bids")
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise ValueError("Agent not found")

    bid = Bid(task_id=task_id, agent_id=agent_id, price=price)
    db.add(bid)
    db.flush()
    record_event(
        db,
        EventType.bid_submitted,
        task_id=task_id,
        agent_id=agent_id,
        payload={"bid_id": bid.id, "price": price},
    )
    db.commit()
    db.refresh(bid)
    return bid


def list_task_bids(db: Session, *, task_id: int) -> list[Bid]:
    return list(
        db.scalars(select(Bid).where(Bid.task_id == task_id).order_by(Bid.id.desc())).all()
    )


def assign_task(db: Session, *, task_id: int, agent_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise ValueError("Agent not found")
    if task.status != TaskStatus.open:
        raise ValueError("Task is not open")

    task.status = TaskStatus.assigned
    task.assigned_agent_id = agent_id

    bids = list(
        db.scalars(select(Bid).where(Bid.task_id == task.id, Bid.status == BidStatus.submitted)).all()
    )
    for bid in bids:
        bid.status = BidStatus.accepted if bid.agent_id == agent_id else BidStatus.rejected

    record_event(db, EventType.task_assigned, task_id=task.id, agent_id=agent.id)
    db.commit()
    db.refresh(task)
    return task


def submit_artifact(
    db: Session, *, task_id: int, agent_id: int, hash_value: str, quality_score: float
) -> Artifact:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.assigned_agent_id != agent_id:
        raise ValueError("Only assigned agent can submit artifact")
    if task.status != TaskStatus.assigned:
        raise ValueError("Task must be assigned before delivery")

    artifact = Artifact(
        task_id=task_id,
        agent_id=agent_id,
        hash=hash_value,
        quality_score=quality_score,
    )
    db.add(artifact)
    task.status = TaskStatus.delivered
    db.flush()
    record_event(
        db,
        EventType.artifact_delivered,
        task_id=task_id,
        agent_id=agent_id,
        payload={"artifact_id": artifact.id, "quality": quality_score},
    )
    db.commit()
    db.refresh(artifact)
    return artifact


def verify_task(db: Session, *, task_id: int, approved: bool) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status != TaskStatus.delivered:
        raise ValueError("Task must be delivered before verification")

    task.status = TaskStatus.verified if approved else TaskStatus.disputed
    record_event(
        db,
        EventType.task_verified,
        task_id=task_id,
        payload={"approved": approved},
    )
    db.commit()
    db.refresh(task)
    return task


def dispute_task(db: Session, *, task_id: int, reason: str) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status not in {TaskStatus.delivered, TaskStatus.verified, TaskStatus.assigned}:
        raise ValueError("Task cannot be disputed in current state")

    task.status = TaskStatus.disputed
    record_event(
        db,
        EventType.task_disputed,
        task_id=task.id,
        agent_id=task.assigned_agent_id,
        payload={"reason": reason},
    )
    db.commit()
    db.refresh(task)
    return task


def accept_task(db: Session, *, task_id: int) -> tuple[Task, float, float]:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status != TaskStatus.verified:
        raise ValueError("Task must be verified before acceptance")

    task.status = TaskStatus.accepted
    immediate, holdback = escrow.release_on_accept(task)
    if task.assigned_agent_id:
        agent = db.get(Agent, task.assigned_agent_id)
        last_artifact = db.scalar(
            select(Artifact)
            .where(Artifact.task_id == task.id)
            .order_by(Artifact.id.desc())
            .limit(1)
        )
        if agent and last_artifact:
            new_rep = reputation.update_reputation(agent, last_artifact.quality_score)
            record_event(
                db,
                EventType.reputation_updated,
                task_id=task.id,
                agent_id=agent.id,
                payload={"new_reputation": new_rep},
            )

    record_event(
        db,
        EventType.payout_released,
        task_id=task.id,
        agent_id=task.assigned_agent_id,
        payload={"paid_now": immediate, "holdback": holdback},
    )
    db.commit()
    db.refresh(task)
    return task, immediate, holdback


def list_events(db: Session) -> list:
    from .models import LedgerEvent

    return list(db.scalars(select(LedgerEvent).order_by(LedgerEvent.id.desc())).all())
