from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class PresenceState:
    goal: Optional[str] = None
    phase: Optional[str] = None
    focus: Optional[str] = None
    intent: Optional[str] = None
    context: Optional[str] = None
    task_id: Optional[str] = None
    confidence: float = 0.0
    updated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "phase": self.phase,
            "focus": self.focus,
            "intent": self.intent,
            "context": self.context,
            "task_id": self.task_id,
            "confidence": self.confidence,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    def reset(self, reason: Optional[str] = None) -> None:
        if reason:
            self.metadata["reset_reason"] = reason
        self.goal = None
        self.phase = None
        self.focus = None
        self.intent = None
        self.context = None
        self.task_id = None
        self.confidence = 0.0
        self.updated_at = None
