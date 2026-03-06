from __future__ import annotations

from bisect import bisect_left, bisect_right, insort
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple


@dataclass
class TemporalIndex:
    _index: Dict[datetime, List[str]] = field(default_factory=dict)
    _sorted_keys: List[datetime] = field(default_factory=list)

    def _normalize(self, timestamp: datetime) -> datetime:
        """Ensure timestamp is timezone-aware UTC."""
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp

    def add(self, timestamp: datetime, belief_id: str) -> None:
        ts = self._normalize(timestamp)
        if ts not in self._index:
            self._index[ts] = []
            insort(self._sorted_keys, ts)
        if belief_id not in self._index[ts]:
            self._index[ts].append(belief_id)

    def remove(self, timestamp: datetime, belief_id: str) -> None:
        ts = self._normalize(timestamp)
        if ts not in self._index:
            return
        ids = self._index[ts]
        if belief_id in ids:
            ids.remove(belief_id)
        if not ids:
            del self._index[ts]
            idx = bisect_left(self._sorted_keys, ts)
            if idx < len(self._sorted_keys) and self._sorted_keys[idx] == ts:
                self._sorted_keys.pop(idx)

    def query_range(self, start: datetime, end: datetime) -> List[str]:
        start_ts = self._normalize(start)
        end_ts = self._normalize(end)
        if start_ts > end_ts:
            return []
        left = bisect_left(self._sorted_keys, start_ts)
        right = bisect_right(self._sorted_keys, end_ts)
        results: List[str] = []
        for key in self._sorted_keys[left:right]:
            results.extend(sorted(self._index[key]))
        return results

    def ingest(self, entries: Iterable[Tuple[datetime, str]]) -> None:
        for timestamp, belief_id in entries:
            self.add(timestamp, belief_id)
