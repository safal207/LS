from __future__ import annotations

VALID_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"planning", "cancelled"},
    "planning": {"running", "failed", "cancelled"},
    "running": {"waiting_approval", "blocked", "failed", "completed", "cancelled"},
    "waiting_approval": {"running", "blocked", "cancelled"},
    "blocked": {"running", "cancelled", "failed"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def can_transition(current: str, new: str) -> bool:
    return new in VALID_TRANSITIONS.get(current, set())
