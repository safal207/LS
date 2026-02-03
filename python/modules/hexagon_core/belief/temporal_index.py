from __future__ import annotations

from bisect import bisect_left, bisect_right, insort
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Set, Tuple


@dataclass
class TemporalIndex:
    _index: Dict[datetime, Set[str]] = field(default_factory=dict)
    _sorted_keys: List[datetime] = field(default_factory=list)

    def add(self, timestamp: datetime, belief_id: str) -> None:
        if timestamp not in self._index:
            self._index[timestamp] = set()
            insort(self._sorted_keys, timestamp)
        self._index[timestamp].add(belief_id)

    def remove(self, timestamp: datetime, belief_id: str) -> None:
        if timestamp not in self._index:
            return
        ids = self._index[timestamp]
        ids.discard(belief_id)
        if not ids:
            del self._index[timestamp]
            idx = bisect_left(self._sorted_keys, timestamp)
            if idx < len(self._sorted_keys) and self._sorted_keys[idx] == timestamp:
                self._sorted_keys.pop(idx)

    def query_range(self, start: datetime, end: datetime) -> List[str]:
        if start > end:
            return []
        left = bisect_left(self._sorted_keys, start)
        right = bisect_right(self._sorted_keys, end)
        results: List[str] = []
        for key in self._sorted_keys[left:right]:
            results.extend(self._index[key])
        return results

    def ingest(self, entries: Iterable[Tuple[datetime, str]]) -> None:
        for timestamp, belief_id in entries:
            self.add(timestamp, belief_id)
