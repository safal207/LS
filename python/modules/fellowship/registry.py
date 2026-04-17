from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FellowshipGroup:
    fellowship_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    visibility: str = "private"  # private | public
    participants: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fellowship_id": self.fellowship_id,
            "name": self.name,
            "visibility": self.visibility,
            "participants": list(self.participants),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "audit_log": list(self.audit_log),
        }


class FellowshipRegistry:
    """In-memory registry helper used by persistence layer and tests."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        raw = dict(payload or {})
        self.groups: dict[str, FellowshipGroup] = {}
        for row in list(raw.get("groups") or []):
            if not isinstance(row, dict):
                continue
            group = FellowshipGroup(
                fellowship_id=str(row.get("fellowship_id") or str(uuid4())),
                name=str(row.get("name") or ""),
                visibility=str(row.get("visibility") or "private"),
                participants=[
                    str(pid) for pid in list(row.get("participants") or []) if str(pid).strip()
                ],
                created_at=str(row.get("created_at") or _utc_now()),
                updated_at=str(row.get("updated_at") or _utc_now()),
                audit_log=list(row.get("audit_log") or []),
            )
            self.groups[group.fellowship_id] = group

    def create_group(self, *, name: str, visibility: str = "private") -> FellowshipGroup:
        vis = str(visibility or "private").lower()
        if vis not in {"private", "public"}:
            vis = "private"
        group = FellowshipGroup(name=str(name or "").strip(), visibility=vis)
        group.audit_log.append({"event": "group_created", "timestamp": _utc_now(), "visibility": vis})
        self.groups[group.fellowship_id] = group
        return group

    def join_group(self, *, fellowship_id: str, participant_id: str) -> FellowshipGroup | None:
        group = self.groups.get(str(fellowship_id or ""))
        if group is None:
            return None
        pid = str(participant_id or "").strip()
        if not pid:
            return group
        if pid not in group.participants:
            group.participants.append(pid)
            group.updated_at = _utc_now()
            group.audit_log.append({"event": "participant_joined", "participant_id": pid, "timestamp": group.updated_at})
        return group

    def to_dict(self) -> dict[str, Any]:
        return {
            "groups": [group.to_dict() for group in self.groups.values()],
            "updated_at": _utc_now(),
        }
