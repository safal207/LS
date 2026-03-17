from __future__ import annotations

from .models import Task


DEFAULT_HOLDBACK_RATE = 0.2


def lock_reward(task: Task) -> None:
    task.escrow_locked = task.reward
    task.holdback_locked = 0.0
    task.paid_out = 0.0


def release_on_accept(task: Task, *, holdback_rate: float = DEFAULT_HOLDBACK_RATE) -> tuple[float, float]:
    holdback_rate = min(max(holdback_rate, 0.0), 0.95)
    holdback = round(task.escrow_locked * holdback_rate, 4)
    immediate = round(task.escrow_locked - holdback, 4)

    task.paid_out += immediate
    task.holdback_locked = holdback
    task.escrow_locked = 0.0

    return immediate, holdback
