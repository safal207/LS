from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class DecisionRecord:
    record_id: str
    choice: str
    alternatives: List[str]
    reasons: List[str]
    consequences: Dict[str, Any]
    system_state_before: str
    system_state_after: str
    thread_id: str
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "choice": self.choice,
            "alternatives": list(self.alternatives),
            "reasons": list(self.reasons),
            "consequences": dict(self.consequences),
            "system_state_before": self.system_state_before,
            "system_state_after": self.system_state_after,
            "thread_id": self.thread_id,
            "success": self.success,
            "timestamp": self.timestamp,
        }


@dataclass
class DecisionMemoryProtocol:
    records: List[DecisionRecord] = field(default_factory=list)

    def record_decision(
        self,
        *,
        choice: str,
        alternatives: List[str],
        reasons: List[str],
        consequences: Dict[str, Any],
        system_state_before: str,
        system_state_after: str,
        thread_id: str,
        success: bool,
    ) -> DecisionRecord:
        record = DecisionRecord(
            record_id=str(uuid.uuid4()),
            choice=choice,
            alternatives=list(alternatives),
            reasons=list(reasons),
            consequences=dict(consequences),
            system_state_before=system_state_before,
            system_state_after=system_state_after,
            thread_id=thread_id,
            success=success,
        )
        self.records.append(record)
        return record

    def recent_for_model(self, model: str, limit: int = 5) -> List[DecisionRecord]:
        matches = [record for record in self.records if record.choice == model]
        return matches[-limit:]

    def success_rate(self, model: str) -> float:
        matches = [record for record in self.records if record.choice == model]
        if not matches:
            return 0.0
        successes = sum(1 for record in matches if record.success)
        return successes / len(matches)
