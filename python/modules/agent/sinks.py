from __future__ import annotations

import json
from typing import Any, Protocol


class EventSink(Protocol):
    def emit(self, event: dict[str, Any]) -> None: ...


class NullSink:
    def emit(self, event: dict[str, Any]) -> None:
        return


class PrintSink:
    def emit(self, event: dict[str, Any]) -> None:
        print(json.dumps(event, ensure_ascii=False))


def build_event_sink(name: str | None) -> EventSink:
    if not name:
        return NullSink()
    name = name.lower()
    if name == "print":
        return PrintSink()
    return NullSink()
