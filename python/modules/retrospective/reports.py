from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RetrospectiveReport:
    timestamp: str
    strong_routes: list[str] = field(default_factory=list)
    weak_routes: list[str] = field(default_factory=list)
    strong_coalitions: list[str] = field(default_factory=list)
    weak_coalitions: list[str] = field(default_factory=list)
    stale_modules: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
