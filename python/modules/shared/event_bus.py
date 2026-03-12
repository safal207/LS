from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, DefaultDict, List


class EventBus:
    """Simple in-process pub/sub for runtime module coordination."""

    def __init__(self):
        self.subscribers: DefaultDict[str, List[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self.subscribers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        event_type = getattr(event, "type", None)
        if not event_type:
            return
        for handler in self.subscribers.get(event_type, []):
            handler(event)
