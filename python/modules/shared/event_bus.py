from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
import logging
import threading
from typing import Any, Callable, DefaultDict, List


logger = logging.getLogger(__name__)


class EventBus:
    """Simple in-process pub/sub for runtime module coordination."""

    def __init__(self, max_workers: int = 4):
        self.subscribers: DefaultDict[str, List[Callable[[Any], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="event-bus")

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        with self._lock:
            self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        with self._lock:
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
        with self._lock:
            if event_type is not None:
                return len(self.subscribers.get(event_type, []))
            return sum(len(handlers) for handlers in self.subscribers.values())

    def subscriber_snapshot(self) -> dict[str, int]:
        with self._lock:
            return {event_type: len(handlers) for event_type, handlers in self.subscribers.items()}

    def publish(self, event: Any) -> None:
        event_type = getattr(event, "type", None)
        if not event_type:
            return
        with self._lock:
            handlers = list(self.subscribers.get(event_type, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.exception("Event handler failed for event_type=%s: %s", event_type, exc)

    def publish_async(self, event: Any) -> list[Future]:
        event_type = getattr(event, "type", None)
        if not event_type:
            return []

        with self._lock:
            handlers = list(self.subscribers.get(event_type, []))

        futures: list[Future] = []
        for handler in handlers:
            futures.append(self._executor.submit(self._safe_dispatch, event_type, handler, event))
        return futures

    @staticmethod
    def _safe_dispatch(event_type: str, handler: Callable[[Any], None], event: Any) -> None:
        try:
            handler(event)
        except Exception as exc:
            logger.exception("Async event handler failed for event_type=%s: %s", event_type, exc)
