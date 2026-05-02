from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from . import escrow, reputation
from .executor import execute_task as execute_task_content
from .ledger import record_event
from .models import (
    Agent,
    Artifact,
    Bid,
    BidStatus,
    EventType,
    GovernanceParam,
    Project,
    Settlement,
    SettlementStatus,
    Task,
    TaskStatus,
    VerificationReview,
    VerificationStage,
)
from .verification import evaluate_artifact

DEFAULT_GOVERNANCE: dict[str, float] = {
    "holdback_rate": 0.2,
    "holdback_days": 7,
    "auction_weight_price": 0.5,
    "auction_weight_rep": 0.3,
    "auction_weight_speed": 0.2,
    "rollback_penalty": 0.15,
}


def ensure_governance_defaults(db: Session) -> None:
    changed = False
    for key, value in DEFAULT_GOVERNANCE.items():
        existing = db.get(GovernanceParam, key)
        if existing is None:
            db.add(GovernanceParam(key=key, value=value))
            changed = True
    if changed:
        db.commit()


def get_param(db: Session, key: str) -> float:
    param = db.get(GovernanceParam, key)
    if param is None:
        raise ValueError(f"Governance param '{key}' not found")
    return param.value


def create_agent(db: Session, *, name: str) -> Agent:
    agent = Agent(name=name)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def list_agents(db: Session) -> list[Agent]:
    return list(db.scalars(select(Agent).order_by(Agent.id)).all())


def create_project(db: Session, *, name: str, treasury_balance: float) -> Project:
    project = Project(name=name, treasury_balance=treasury_balance)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.id)).all())


def create_task(
    db: Session,
    *,
    project_id: int,
    title: str,
    description: str,
    reward: float,
    use_case: str = "generic",
) -> Task:
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")
    if project.treasury_balance < reward:
        raise ValueError("Insufficient project treasury balance")

    project.treasury_balance = round(project.treasury_balance - reward, 4)
    task = Task(
        project_id=project_id,
        title=title,
        description=description,
        reward=reward,
        use_case=use_case,
    )
    escrow.lock_reward(task)
    db.add(task)
    db.flush()
    record_event(
        db,
        EventType.treasury_updated,
        task_id=task.id,
        payload={"project_id": project_id, "balance": project.treasury_balance},
    )
    record_event(
        db,
        EventType.task_created,
        task_id=task.id,
        payload={"title": title, "reward": reward, "project_id": project_id},
    )
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session) -> list[Task]:
    return list(db.scalars(select(Task).order_by(Task.id.desc())).all())


def submit_bid(db: Session, *, task_id: int, agent_id: int, price: float, eta_hours: int) -> Bid:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status != TaskStatus.open:
        raise ValueError("Only open tasks accept bids")
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise ValueError("Agent not found")

    bid = Bid(task_id=task_id, agent_id=agent_id, price=price, eta_hours=eta_hours)
    db.add(bid)
    db.flush()
    record_event(
        db,
        EventType.bid_submitted,
        task_id=task_id,
        agent_id=agent_id,
        payload={"bid_id": bid.id, "price": price, "eta_hours": eta_hours},
    )
    db.commit()
    db.refresh(bid)
    return bid


def list_task_bids(db: Session, *, task_id: int) -> list[Bid]:
    return list(db.scalars(select(Bid).where(Bid.task_id == task_id).order_by(Bid.id.desc())).all())


def _resolve_bids(db: Session, *, task: Task, selected_agent_id: int) -> None:
    bids = list(
        db.scalars(select(Bid).where(Bid.task_id == task.id, Bid.status == BidStatus.submitted)).all()
    )
    for bid in bids:
        bid.status = BidStatus.accepted if bid.agent_id == selected_agent_id else BidStatus.rejected


def _bid_score(
    db: Session,
    bid: Bid,
    price_weight: float | None = None,
    rep_weight: float | None = None,
    speed_weight: float | None = None,
) -> float:
    pw = price_weight if price_weight is not None else get_param(db, "auction_weight_price")
    rw = rep_weight if rep_weight is not None else get_param(db, "auction_weight_rep")
    sw = speed_weight if speed_weight is not None else get_param(db, "auction_weight_speed")

    # Use joined agent if available, otherwise fetch from DB
    agent = bid.agent if bid.agent else db.get(Agent, bid.agent_id)
    rep = agent.reputation if agent else 1.0
    price_score = 1.0 / (1.0 + bid.price)
    speed_score = 1.0 / (1.0 + bid.eta_hours)
    return pw * price_score + rw * rep + sw * speed_score


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
    _resolve_bids(db, task=task, selected_agent_id=agent_id)
    record_event(db, EventType.task_assigned, task_id=task.id, agent_id=agent.id)
    db.commit()
    db.refresh(task)
    return task


def assign_best_bid(db: Session, *, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status != TaskStatus.open:
        raise ValueError("Task is not open")

    # Fetch weights once to avoid N+1 queries in the loop
    weights = {
        "price_weight": get_param(db, "auction_weight_price"),
        "rep_weight": get_param(db, "auction_weight_rep"),
        "speed_weight": get_param(db, "auction_weight_speed"),
    }

    # Fetch bids with agents joined to avoid N+1 queries for agent reputation
    stmt = (
        select(Bid)
        .options(joinedload(Bid.agent))
        .where(Bid.task_id == task_id, Bid.status == BidStatus.submitted)
    )
    bids = list(db.scalars(stmt).all())

    if not bids:
        raise ValueError("No submitted bids for task")

    best_bid = max(bids, key=lambda bid: _bid_score(db, bid, **weights))
    return assign_task(db, task_id=task_id, agent_id=best_bid.agent_id)


def submit_artifact(
    db: Session,
    *,
    task_id: int,
    agent_id: int,
    hash_value: str,
    quality_score: float,
    content: str = "",
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
        content=content,
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


def execute_task(db: Session, *, task_id: int) -> Artifact:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status == TaskStatus.open:
        task = assign_best_bid(db, task_id=task_id)
    if task.assigned_agent_id is None:
        raise ValueError("Task must be assigned before execution")
    if task.status != TaskStatus.assigned:
        raise ValueError("Task must be assigned before execution")

    content = execute_task_content(task)
    quality = evaluate_artifact(task, content)["quality_score"]
    hash_value = hashlib.sha256(content.encode("utf-8")).hexdigest()[:64]
    artifact = submit_artifact(
        db,
        task_id=task.id,
        agent_id=task.assigned_agent_id,
        hash_value=hash_value,
        quality_score=float(quality),
        content=content,
    )
    record_event(db, EventType.task_executed, task_id=task.id, agent_id=task.assigned_agent_id)
    return artifact


def verify_stage(
    db: Session,
    *,
    task_id: int,
    stage: VerificationStage,
    passed: bool,
    note: str,
    impact_score: float | None,
) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if stage == VerificationStage.impact:
        if task.status not in {TaskStatus.delivered, TaskStatus.verified}:
            raise ValueError("Task must be delivered/verified before impact stage")
    elif task.status != TaskStatus.delivered:
        raise ValueError("Task must be delivered before staged verification")

    if stage == VerificationStage.auto:
        task.auto_check_passed = passed
    elif stage == VerificationStage.reviewer:
        task.reviewer_check_passed = passed
    elif stage == VerificationStage.impact:
        task.impact_score = impact_score

    review = VerificationReview(task_id=task_id, stage=stage, passed=passed, note=note)
    db.add(review)
    record_event(
        db,
        EventType.verification_stage_recorded,
        task_id=task_id,
        agent_id=task.assigned_agent_id,
        payload={"stage": stage.value, "passed": passed, "note": note},
    )

    if not passed and stage in {VerificationStage.auto, VerificationStage.reviewer}:
        task.status = TaskStatus.disputed
        record_event(db, EventType.task_disputed, task_id=task_id, payload={"reason": note})
    elif task.auto_check_passed and task.reviewer_check_passed:
        task.status = TaskStatus.verified
        record_event(db, EventType.task_verified, task_id=task_id, payload={"approved": True})

    db.commit()
    db.refresh(task)
    return task


def verify_task(db: Session, *, task_id: int, approved: bool) -> Task:
    return verify_stage(
        db,
        task_id=task_id,
        stage=VerificationStage.reviewer,
        passed=approved,
        note="legacy verify endpoint",
        impact_score=None,
    )


def auto_loop_task(db: Session, *, task_id: int) -> Task:
    artifact = execute_task(db, task_id=task_id)
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    eval_result = evaluate_artifact(task, artifact.content)

    task = verify_stage(
        db,
        task_id=task.id,
        stage=VerificationStage.auto,
        passed=bool(eval_result["auto_pass"]),
        note=str(eval_result["note"]),
        impact_score=None,
    )
    if task.status == TaskStatus.disputed:
        return task

    task = verify_stage(
        db,
        task_id=task.id,
        stage=VerificationStage.reviewer,
        passed=bool(eval_result["reviewer_pass"]),
        note="auto reviewer simulation",
        impact_score=None,
    )
    if task.status == TaskStatus.disputed:
        return task

    task = verify_stage(
        db,
        task_id=task.id,
        stage=VerificationStage.impact,
        passed=True,
        note="impact measured",
        impact_score=float(eval_result["impact_score"]),
    )

    if task.status == TaskStatus.verified:
        accept_task(db, task_id=task.id)
        run_settlement(db)

    task = db.get(Task, task.id)
    record_event(db, EventType.autoloop_completed, task_id=task_id)
    db.commit()
    return task


def dispute_task(db: Session, *, task_id: int, reason: str) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.status not in {TaskStatus.delivered, TaskStatus.verified, TaskStatus.assigned}:
        raise ValueError("Task cannot be disputed in current state")

    task.status = TaskStatus.disputed
    penalty = get_param(db, "rollback_penalty")
    if task.assigned_agent_id:
        agent = db.get(Agent, task.assigned_agent_id)
        if agent:
            agent.reputation = max(0.0, round(agent.reputation * (1 - penalty), 4))
            record_event(
                db,
                EventType.reputation_updated,
                task_id=task.id,
                agent_id=agent.id,
                payload={"new_reputation": agent.reputation, "penalized": True},
            )

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

    holdback_rate = get_param(db, "holdback_rate")
    holdback_days = int(get_param(db, "holdback_days"))

    task.status = TaskStatus.accepted
    immediate, holdback = escrow.release_on_accept(task, holdback_rate=holdback_rate)

    if holdback > 0:
        settlement = Settlement(
            task_id=task.id,
            amount=holdback,
            release_at=datetime.utcnow() + timedelta(days=holdback_days),
        )
        db.add(settlement)
        record_event(
            db,
            EventType.settlement_scheduled,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            payload={"amount": holdback, "release_in_days": holdback_days},
        )

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


def list_settlements(db: Session) -> list[Settlement]:
    return list(db.scalars(select(Settlement).order_by(Settlement.id.desc())).all())


def run_settlement(db: Session) -> tuple[int, float]:
    now = datetime.utcnow()
    pending = list(
        db.scalars(
            select(Settlement).where(
                Settlement.status == SettlementStatus.pending,
                Settlement.release_at <= now,
            )
        ).all()
    )
    released_amount = 0.0
    for settlement in pending:
        settlement.status = SettlementStatus.released
        task = db.get(Task, settlement.task_id)
        if task:
            task.holdback_locked = max(0.0, round(task.holdback_locked - settlement.amount, 4))
            task.paid_out += settlement.amount
            if task.holdback_locked <= 0 and task.status == TaskStatus.accepted:
                task.status = TaskStatus.closed
        released_amount += settlement.amount
        record_event(
            db,
            EventType.settlement_released,
            task_id=settlement.task_id,
            payload={"amount": settlement.amount},
        )
    db.commit()
    return len(pending), round(released_amount, 4)


def list_governance(db: Session) -> list[GovernanceParam]:
    return list(db.scalars(select(GovernanceParam).order_by(GovernanceParam.key)).all())


def update_governance(db: Session, *, key: str, value: float) -> GovernanceParam:
    param = db.get(GovernanceParam, key)
    if param is None:
        raise ValueError("Governance parameter not found")
    param.value = value
    record_event(db, EventType.governance_updated, payload={"key": key, "value": value})
    db.commit()
    db.refresh(param)
    return param


def list_events(db: Session) -> list:
    from .models import LedgerEvent

    return list(db.scalars(select(LedgerEvent).order_by(LedgerEvent.id.desc())).all())
