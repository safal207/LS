from dataclasses import dataclass
from datetime import datetime
from typing import List, Any, Optional
import bisect

@dataclass
class IndexedItem:
    timestamp: datetime
    item: Any

    # Comparison methods for bisect
    def __lt__(self, other):
        return self.timestamp < other.timestamp

class TemporalIndex:
    """
    Maintains a time-ordered index of items.
    """
    def __init__(self):
        self._items: List[IndexedItem] = []

    def add(self, item: Any, timestamp: datetime):
        entry = IndexedItem(timestamp, item)
        # Optimized insertion O(log N) + O(N) shift, better than O(N log N) sort
        # bisect.insort uses < operator defined in IndexedItem
        bisect.insort(self._items, entry)

    def remove_item(self, item: Any):
        # O(N) removal
        self._items = [x for x in self._items if x.item != item]

    def get_range(self, start: datetime, end: datetime) -> List[Any]:
        return [
            x.item for x in self._items
            if start <= x.timestamp <= end
        ]
