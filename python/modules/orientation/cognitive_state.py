from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CognitiveSnapshot:
    snapshot_id: str
    timestamp: float
    state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "state": copy.deepcopy(self.state),
        }


class CognitiveStateCenter:
    """Mutable center for consolidated cognitive state with snapshot/restore/diff APIs."""

    def __init__(self, *, max_snapshots: int = 128) -> None:
        self.max_snapshots = max(1, int(max_snapshots))
        self._state: dict[str, Any] = self._normalize({})
        self._snapshots: dict[str, CognitiveSnapshot] = {}
        self._order: list[str] = []

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "beliefs": list(raw.get("beliefs") or []),
            "causal_edges": list(raw.get("causal_edges") or []),
            "temporal_nodes": list(raw.get("temporal_nodes") or []),
            "mission_state": dict(raw.get("mission_state") or {}),
            "cot_trace": list(raw.get("cot_trace") or []),
        }

    def update_state(self, *, create_snapshot: bool = False, **parts: Any) -> dict[str, Any]:
        next_state = copy.deepcopy(self._state)
        for key in ("beliefs", "causal_edges", "temporal_nodes", "mission_state", "cot_trace"):
            if key in parts and parts[key] is not None:
                if key == "mission_state":
                    next_state[key] = dict(parts[key])
                else:
                    next_state[key] = list(parts[key])
        self._state = self._normalize(next_state)
        if create_snapshot:
            return self.create_snapshot().to_dict()
        return self.get_cognitive_snapshot()

    def create_snapshot(self) -> CognitiveSnapshot:
        snap = CognitiveSnapshot(
            snapshot_id=str(uuid.uuid4()),
            timestamp=time.time(),
            state=copy.deepcopy(self._state),
        )
        self._snapshots[snap.snapshot_id] = snap
        self._order.append(snap.snapshot_id)
        while len(self._order) > self.max_snapshots:
            evicted = self._order.pop(0)
            self._snapshots.pop(evicted, None)
        return snap

    def get_cognitive_snapshot(self, snapshot_id: str | None = None) -> dict[str, Any]:
        if snapshot_id is None:
            return {
                "snapshot_id": self._order[-1] if self._order else None,
                "timestamp": None,
                "state": copy.deepcopy(self._state),
            }
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise KeyError(f"unknown snapshot_id: {snapshot_id}")
        return snap.to_dict()

    def restore_cognitive_snapshot(
        self,
        *,
        snapshot_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if payload is not None:
            state = payload.get("state", payload)
            self._state = self._normalize(dict(state))
            return self.get_cognitive_snapshot()

        if snapshot_id is None:
            raise ValueError("provide snapshot_id or payload")
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise KeyError(f"unknown snapshot_id: {snapshot_id}")
        self._state = self._normalize(copy.deepcopy(snap.state))
        return self.get_cognitive_snapshot(snapshot_id)

    def diff_cognitive_snapshots(self, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        a_state = self._normalize(a.get("state", a))
        b_state = self._normalize(b.get("state", b))

        def _len(key: str, state: dict[str, Any]) -> int:
            value = state.get(key)
            return len(value) if isinstance(value, list) else 0

        mission_changed = a_state.get("mission_state") != b_state.get("mission_state")
        return {
            "beliefs_delta": _len("beliefs", b_state) - _len("beliefs", a_state),
            "causal_edges_delta": _len("causal_edges", b_state) - _len("causal_edges", a_state),
            "temporal_nodes_delta": _len("temporal_nodes", b_state) - _len("temporal_nodes", a_state),
            "cot_trace_delta": _len("cot_trace", b_state) - _len("cot_trace", a_state),
            "mission_state_changed": mission_changed,
        }
