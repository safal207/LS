from __future__ import annotations

import queue
import time
from typing import Any, Callable, Optional

from llm.temporal import TemporalContext

from .events import AgentEvent, EventType


class AgentLoop:
    def __init__(
        self,
        input_queue: Optional[queue.Queue] = None,
        output_queue: Optional[queue.Queue] = None,
        *,
        llm: Any | None = None,
        handler: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[AgentEvent], None]] = None,
        temporal: TemporalContext | None = None,
        temporal_enabled: bool = True,
    ) -> None:
        if (llm is None) == (handler is None):
            raise ValueError("Provide exactly one of llm or handler")

        self.input_queue = input_queue
        self.output_queue = output_queue
        self.llm = llm
        self.handler = handler
        self.on_event = on_event
        self.running = False

        self.temporal = temporal if temporal_enabled else None
        if temporal_enabled and self.temporal is None:
            self.temporal = TemporalContext()

    def _emit(self, event_type: EventType, payload: dict | None = None) -> None:
        if not self.on_event:
            return
        self.on_event(AgentEvent(type=event_type, payload=payload or {}))

    def _transition(self, state: str) -> None:
        if self.temporal:
            self.temporal.transition(state)
        self._emit("state_changed", {"state": state})

    def _format_response(self, response: Any) -> Any:
        if self.llm and hasattr(self.llm, "format_response"):
            try:
                return self.llm.format_response(response)
            except Exception:
                return response
        return response

    def _process(self, question: str) -> Any:
        if self.llm:
            return self.llm.generate_response(question)
        return self.handler(question)

    def handle_item(self, item: dict) -> None:
        try:
            self._emit("input_received", {"item": item})
            self._transition("listening")

            if item.get("type") != "question":
                return

            question = item.get("text", "")
            self._emit("llm_started", {"question": question})
            self._transition("thinking")

            start = time.time()
            result = self._process(question)
            duration = time.time() - start

            self._emit("llm_finished", {
                "question": question,
                "duration": duration,
                "success": result is not None,
            })

            if result is not None or self.handler is not None:
                self._transition("responding")

            payload = None
            if isinstance(result, dict):
                payload = result
            elif result is not None:
                payload = {
                    "question": question,
                    "response": self._format_response(result),
                    "generation_time": duration,
                    "timestamp": time.time(),
                }

            if payload is not None:
                if self.output_queue is not None:
                    try:
                        self.output_queue.put_nowait(payload)
                    except queue.Full:
                        self._emit("error", {"message": "output_queue_full"})
                    else:
                        self._emit("output_ready", payload)
                else:
                    self._emit("output_ready", payload)

        except Exception as exc:
            self._emit("error", {"message": str(exc)})
        finally:
            self._transition("idle")

    def handle_input(self, text: str) -> None:
        self.handle_item({
            "type": "question",
            "text": text,
            "timestamp": time.time(),
        })

    def submit(self, text: str) -> None:
        if self.input_queue is None:
            self.handle_input(text)
            return
        self.input_queue.put({
            "type": "question",
            "text": text,
            "timestamp": time.time(),
        })

    def run(self) -> None:
        if self.input_queue is None:
            raise RuntimeError("input_queue is required for run()")

        self.running = True
        while self.running:
            try:
                item = self.input_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self.handle_item(item)
            finally:
                try:
                    self.input_queue.task_done()
                except Exception:
                    pass

    def stop(self) -> None:
        self.running = False
