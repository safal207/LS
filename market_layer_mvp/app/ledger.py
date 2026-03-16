from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .models import EventType, LedgerEvent


def record_event(
    db: Session,
    event_type: EventType,
    *,
    task_id: int | None = None,
    agent_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> LedgerEvent:
    event = LedgerEvent(
        event_type=event_type,
        task_id=task_id,
        agent_id=agent_id,
        payload=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(event)
    db.flush()
    return event
