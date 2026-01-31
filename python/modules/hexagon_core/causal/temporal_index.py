from dataclasses import dataclass
from datetime import datetime
from typing import List, Any, Optional
import bisect

@dataclass
class IndexedItem:
    timestamp: datetime
    item: Any

class TemporalIndex:
    """
    Maintains a time-ordered index of items.
    """
    def __init__(self):
        self._items: List[IndexedItem] = []

    def add(self, item: Any, timestamp: datetime):
        entry = IndexedItem(timestamp, item)
        # Keep sorted by timestamp
        # bisect doesn't support key argument in older python, but python 3.10+ does.
        # Assuming standard python env. If not, separate keys list.
        # Let's use a separate keys list for safety if needed, or just append and sort (slow).
        # Optimization: since we often add "now", it's likely already sorted.

        if not self._items or timestamp >= self._items[-1].timestamp:
            self._items.append(entry)
        else:
            # Find insertion point
            # Linear scan or binary search.
            # Using simple sort for robustness in "starter pack".
            self._items.append(entry)
            self._items.sort(key=lambda x: x.timestamp)

    def remove_item(self, item: Any):
        # O(N) removal
        self._items = [x for x in self._items if x.item != item]

    def get_range(self, start: datetime, end: datetime) -> List[Any]:
        return [
            x.item for x in self._items
            if start <= x.timestamp <= end
        ]
