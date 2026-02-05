from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class AttentionState:
    focus: Optional[str] = None
    confidence: float = 0.0
    last_updated: Optional[float] = None
    history: List[str] = field(default_factory=list)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "focus": self.focus,
            "confidence": self.confidence,
            "last_updated": self.last_updated,
            "history": list(self.history),
        }
