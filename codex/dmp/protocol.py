from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class DecisionRecord:
    decision: str
    context: Dict[str, Any]
    timestamp: str


class DecisionMemoryProtocol:
    def __init__(self) -> None:
        self.records: List[DecisionRecord] = []

    def record_decision(self, *, decision: str, context: Dict[str, Any]) -> DecisionRecord:
        record = DecisionRecord(
            decision=decision,
            context=dict(context),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.records.append(record)
        return record
