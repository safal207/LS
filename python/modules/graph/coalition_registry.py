from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CoalitionRecord:
    coalition_id: str
    route_key: str
    members: list[str]
    intents: list[str] = field(default_factory=list)
    why_tags: list[str] = field(default_factory=list)
    trust_score: float = 0.0
    runs: int = 0
    successes: int = 0
    avg_quality: float = 0.0
    last_used_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CoalitionRecord":
        return cls(
            coalition_id=str(data.get("coalition_id", "")),
            route_key=str(data.get("route_key", "")),
            members=list(data.get("members") or []),
            intents=list(data.get("intents") or []),
            why_tags=list(data.get("why_tags") or []),
            trust_score=float(data.get("trust_score", 0.0) or 0.0),
            runs=int(data.get("runs", 0) or 0),
            successes=int(data.get("successes", 0) or 0),
            avg_quality=float(data.get("avg_quality", 0.0) or 0.0),
            last_used_at=data.get("last_used_at"),
        )


class CoalitionRegistry:
    def __init__(self, path: str | Path = "data/graph_memory/coalitions.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_coalitions(self) -> list[CoalitionRecord]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [CoalitionRecord.from_dict(item) for item in raw if isinstance(item, dict)]

    def get_coalition(self, route_key: str) -> Optional[CoalitionRecord]:
        for coalition in self.list_coalitions():
            if coalition.route_key == route_key:
                return coalition
        return None

    def save_coalition(self, coalition: CoalitionRecord) -> CoalitionRecord:
        coalitions = self.list_coalitions()
        updated = False
        for idx, current in enumerate(coalitions):
            if current.route_key == coalition.route_key:
                coalitions[idx] = coalition
                updated = True
                break
        if not updated:
            coalitions.append(coalition)
        self.path.write_text(
            json.dumps([item.to_dict() for item in coalitions], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return coalition

    def seed_default(self) -> None:
        if self.get_coalition("full_run>local>gonka>mimo"):
            return
        self.save_coalition(
            CoalitionRecord(
                coalition_id="coalition-local-gonka-mimo",
                route_key="full_run>local>gonka>mimo",
                members=["local", "gonka", "mimo"],
                intents=["unknown", "self_presentation", "technical_reasoning"],
                why_tags=["evaluate_reasoning", "evaluate_fit"],
                trust_score=0.6,
            )
        )

    def select_best(
        self,
        *,
        available_backends: list[str],
        intent: str | None = None,
        why_tag: str | None = None,
    ) -> Optional[CoalitionRecord]:
        available = set(available_backends)
        candidates: list[CoalitionRecord] = []
        for coalition in self.list_coalitions():
            if not set(coalition.members).issubset(available):
                continue
            if coalition.intents and intent and intent not in coalition.intents:
                continue
            if coalition.why_tags and why_tag and why_tag not in coalition.why_tags:
                continue
            candidates.append(coalition)
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item.trust_score, item.avg_quality, item.successes), reverse=True)
        return candidates[0]

    def update_after_run(
        self,
        *,
        route_key: str,
        quality_score: float,
        success: bool,
        intent: str | None = None,
        why_tag: str | None = None,
    ) -> CoalitionRecord:
        coalition = self.get_coalition(route_key)
        if coalition is None:
            coalition = CoalitionRecord(
                coalition_id=f"coalition-{route_key.replace('>', '-')}",
                route_key=route_key,
                members=[segment for segment in route_key.split(">") if segment and segment != "full_run" and segment != "refine" and segment != "reuse"],
            )
        if intent and intent not in coalition.intents:
            coalition.intents.append(intent)
        if why_tag and why_tag not in coalition.why_tags:
            coalition.why_tags.append(why_tag)
        runs = coalition.runs
        coalition.runs = runs + 1
        coalition.successes += 1 if success else 0
        coalition.avg_quality = round(((coalition.avg_quality * runs) + quality_score) / (runs + 1), 4)
        coalition.trust_score = round((coalition.trust_score * 0.9) + (0.1 * quality_score), 4)
        coalition.last_used_at = _utc_now()
        return self.save_coalition(coalition)
