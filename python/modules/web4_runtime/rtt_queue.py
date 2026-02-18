from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Generic, Literal, Optional, TypeVar

MessageT = TypeVar("MessageT")
BackpressurePolicy = Literal["dropoldest", "dropnewest", "block", "error"]


@dataclass
class RttQueue(Generic[MessageT]):
    enable_priority_queue: bool = False
    backpressure_policy: BackpressurePolicy = "error"
    fifo: Deque[MessageT] = field(default_factory=deque)
    priority_heap: list[tuple[int, int, MessageT]] = field(default_factory=list)
    oldest_heap: list[tuple[int, int]] = field(default_factory=list)
    live_sequences: set[int] = field(default_factory=set)
    _next_sequence: int = field(default=0, init=False)
    _dropped_priority_count: int = field(default=0, init=False)

    def pending(self) -> int:
        if self.enable_priority_queue:
            return len(self.fifo) + len(self.live_sequences)
        return len(self.fifo)

    def enqueue(self, message: MessageT, priority: Optional[int]) -> None:
        if self.enable_priority_queue:
            self._next_sequence += 1
            normalized_priority = priority if priority is not None else 0
            heapq.heappush(self.priority_heap, (-normalized_priority, self._next_sequence, message))
            if self.backpressure_policy == "dropoldest":
                heapq.heappush(self.oldest_heap, (self._next_sequence, -normalized_priority))
            self.live_sequences.add(self._next_sequence)
            return
        self.fifo.append(message)

    def drop_oldest(self) -> bool:
        if self.enable_priority_queue:
            while self.oldest_heap:
                sequence, _ = heapq.heappop(self.oldest_heap)
                if sequence in self.live_sequences:
                    self.live_sequences.remove(sequence)
                    self._dropped_priority_count += 1
                    return True
            if self.fifo:
                self.fifo.popleft()
                return True
            return False

        if not self.fifo:
            return False
        self.fifo.popleft()
        return True

    def maybe_compact(self, compaction_ratio: int) -> None:
        if not self.enable_priority_queue or not self.priority_heap:
            return
        stale_count = len(self.priority_heap) - len(self.live_sequences)
        if stale_count <= len(self.live_sequences) * compaction_ratio:
            return
        self.priority_heap = [entry for entry in self.priority_heap if entry[1] in self.live_sequences]
        heapq.heapify(self.priority_heap)
        self._dropped_priority_count = 0

    def dequeue(self) -> Optional[MessageT]:
        if self.enable_priority_queue:
            while self.priority_heap:
                _, sequence, item = heapq.heappop(self.priority_heap)
                if sequence in self.live_sequences:
                    self.live_sequences.remove(sequence)
                    return item
            return None
        if not self.fifo:
            return None
        return self.fifo.popleft()

    def clear(self) -> None:
        self.fifo.clear()
        self.priority_heap.clear()
        self.oldest_heap.clear()
        self.live_sequences.clear()
        self._dropped_priority_count = 0
