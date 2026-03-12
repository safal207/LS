from __future__ import annotations

from collections import defaultdict
import logging
from typing import Any, Callable, DefaultDict, List


logger = logging.getLogger(__name__)


class EventBus:
    """Simple in-process pub/sub for runtime module coordination."""

    def __init__(self):
        self.subscribers: DefaultDict[str, List[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        handlers = self.subscribers.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            self.subscribers.pop(event_type, None)

    def subscriber_count(self, event_type: str | None = None) -> int:
        if event_type is not None:
            return len(self.subscribers.get(event_type, []))
        return sum(len(handlers) for handlers in self.subscribers.values())

    def subscriber_snapshot(self) -> dict[str, int]:
        return {event_type: len(handlers) for event_type, handlers in self.subscribers.items()}

    def publish(self, event: Any) -> None:
        event_type = getattr(event, "type", None)
        if not event_type:
            return
        for handler in self.subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as exc:
                logger.exception("Event handler failed for event_type=%s: %s", event_type, exc)
