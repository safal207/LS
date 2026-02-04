from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable, Optional

from llm.temporal import TemporalContext
from cognitive_flow import CognitiveFlow, PresenceState, TransitionEngine

from .event_schema import build_observability_event
from .events import AgentEvent, EventType
from .sinks import EventSink, NullSink


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
        cancel_on_new_input: bool = True,
        cancel_grace_ms: int = 0,
        memory_max_chars: int | None = None,
        metrics_enabled: bool = True,
        event_sink: EventSink | None = None,
        observability_enabled: bool = True,
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
        self.presence = PresenceState()
        self.cognitive_flow = CognitiveFlow(self.presence, TransitionEngine())

        self.memory: dict[str, Any] = {}
        self._task_lock = threading.Lock()
        self._task_counter = 0
        self._active_task_id = 0
        self._active_thread: threading.Thread | None = None
        self._active_cancel: threading.Event | None = None
        self._pending_item: dict | None = None
        self._cancel_grace_until = 0.0

        self.cancel_on_new_input = cancel_on_new_input
        self.cancel_grace_ms = max(cancel_grace_ms, 0)
        self.memory_max_chars = memory_max_chars
        self.metrics_enabled = metrics_enabled
        self.observability_enabled = observability_enabled
        if observability_enabled:
            self.event_sink: EventSink = event_sink or NullSink()
        else:
            self.event_sink = NullSink()

        self.metrics = {
            "inputs": 0,
            "cancellations": 0,
            "outputs": 0,
            "last_latency": 0.0,
            "avg_latency": 0.0,
        }

    def _next_task_id(self) -> int:
        with self._task_lock:
            self._task_counter += 1
            return self._task_counter

    def _set_active(self, task_id: int, cancel_event: threading.Event, thread: threading.Thread | None) -> None:
        self._active_task_id = task_id
        self._active_cancel = cancel_event
        self._active_thread = thread
        self._touch_presence(task_id=task_id)

    def _is_active(self, task_id: int, cancel_event: threading.Event) -> bool:
        if cancel_event.is_set():
            return False
        return task_id == self._active_task_id

    def _touch_presence(self, *, task_id: int | None = None) -> None:
        if self.presence is None:
            return
        self.presence.updated_at = time.time()
        if task_id is not None:
            self.presence.task_id = str(task_id)

    def _step_flow(self, event_type: EventType, payload: dict, *, task_id: int | None = None) -> None:
        if self.cognitive_flow is None:
            return
        before = self.presence.phase if self.presence is not None else None
        try:
            self.cognitive_flow.step({
                "type": event_type,
                "payload": payload,
                "task_id": str(task_id or self._active_task_id),
                "state": self.temporal.state if self.temporal else None,
            })
        except Exception:
            # cognitive flow should be best-effort for now
            pass
            return
        after = self.presence.phase if self.presence is not None else None
        if before != after and after is not None:
            self._emit_observability(
                "phase_transition",
                {"from_phase": before, "to_phase": after, "trigger": event_type},
                task_id=task_id,
            )

    def _emit_observability(self, event_type: EventType, payload: dict, *, task_id: int | None = None) -> None:
        if not self.observability_enabled:
            return
        state = self.temporal.state if self.temporal else None
        event = build_observability_event(
            event_type,
            payload,
            state,
            str(task_id or self._active_task_id),
        )
        if event is None:
            return
        if self.presence is not None:
            event["presence"] = self.presence.snapshot()
        try:
            self.event_sink.emit(event)
        except Exception:
            # observability must never break the agent loop
            pass

    def _emit(self, event_type: EventType, payload: dict | None = None, *, task_id: int | None = None) -> None:
        payload = payload or {}
        self._touch_presence(task_id=task_id)
        self._step_flow(event_type, payload, task_id=task_id)
        if self.on_event:
            self.on_event(AgentEvent(type=event_type, payload=payload))
        self._emit_observability(event_type, payload, task_id=task_id)

    def _transition(self, state: str, *, task_id: int | None = None) -> None:
        if task_id is not None and task_id != self._active_task_id:
            return
        if self.temporal:
            self.temporal.transition(state)
        if self.presence is not None:
            if state == "idle":
                self.presence.reset(reason="agent_idle")
            self.presence.updated_at = time.time()
        self._emit("state_change", {"state": state}, task_id=task_id)

    def _record_metric(self, key: str, value: float | int) -> None:
        with self._task_lock:
            if key in self.metrics and isinstance(value, (int, float)):
                self.metrics[key] = value

    def _track_cancellation(self, cancel_event: threading.Event) -> None:
        if getattr(cancel_event, "_counted", False):
            return
        setattr(cancel_event, "_counted", True)
        self._increment_metric("cancellations", 1)

    def _increment_metric(self, key: str, delta: int = 1) -> None:
        with self._task_lock:
            self.metrics[key] = int(self.metrics.get(key, 0)) + delta

    def _publish_metrics(self) -> None:
        if not self.metrics_enabled:
            return
        with self._task_lock:
            snapshot = dict(self.metrics)
        self._emit("metrics", snapshot)

    def _remember_question(self, question: str) -> None:
        self.memory["last_question"] = question
        self.memory["last_question_ts"] = time.time()
        if self.temporal is not None:
            self.temporal.metadata["last_question"] = question

    def _remember_answer(self, answer: Any, duration: float) -> None:
        if isinstance(answer, str) and self.memory_max_chars:
            answer = answer[: self.memory_max_chars]
        self.memory["last_answer"] = answer
        self.memory["last_answer_ts"] = time.time()
        self.memory["last_duration"] = duration
        if self.temporal is not None:
            self.temporal.metadata["last_answer"] = answer

    def _format_response(self, response: Any) -> Any:
        if self.llm and hasattr(self.llm, "format_response"):
            try:
                return self.llm.format_response(response)
            except Exception:
                return response
        return response

    def _process(self, question: str, cancel_event: threading.Event) -> Any:
        if self.llm:
            try:
                return self.llm.generate_response(question, cancel_event=cancel_event)
            except TypeError:
                return self.llm.generate_response(question)
        return self.handler(question)

    def _cancel_active(self, reason: str) -> None:
        if self._active_thread and self._active_thread.is_alive() and self._active_cancel:
            self._active_cancel.set()
            self._emit("cancelled", {"reason": reason}, task_id=self._active_task_id)
            self._track_cancellation(self._active_cancel)
            if self.cancel_grace_ms:
                self._cancel_grace_until = time.time() + (self.cancel_grace_ms / 1000.0)

    def _start_task(self, item: dict) -> None:
        task_id = self._next_task_id()
        cancel_event = threading.Event()
        thread = threading.Thread(
            target=self._process_item,
            args=(item, task_id, cancel_event),
            daemon=True,
        )
        self._set_active(task_id, cancel_event, thread)
        thread.start()

    def _process_item(self, item: dict, task_id: int, cancel_event: threading.Event) -> None:
        try:
            self._increment_metric("inputs", 1)
            self._emit("input_received", {"item": item}, task_id=task_id)
            self._transition("listening", task_id=task_id)

            if item.get("type") != "question":
                return

            question = item.get("text", "")
            self._remember_question(question)

            if cancel_event.is_set():
                self._emit("cancelled", {"question": question}, task_id=task_id)
                self._track_cancellation(cancel_event)
                return

            self._emit("llm_started", {"question": question}, task_id=task_id)
            self._transition("thinking", task_id=task_id)

            start = time.time()
            result = self._process(question, cancel_event)
            duration = time.time() - start

            if not self._is_active(task_id, cancel_event):
                self._emit("cancelled", {"question": question}, task_id=task_id)
                self._track_cancellation(cancel_event)
                return

            self._emit("llm_finished", {
                "question": question,
                "duration": duration,
                "success": result is not None,
            }, task_id=task_id)

            if result is not None or self.handler is not None:
                self._transition("responding", task_id=task_id)

            payload = None
            if isinstance(result, dict):
                payload = result
            elif result is not None:
                formatted = self._format_response(result)
                self._remember_answer(formatted, duration)
                payload = {
                    "question": question,
                    "response": formatted,
                    "generation_time": duration,
                    "timestamp": time.time(),
                }

            if payload is not None:
                self._increment_metric("outputs", 1)
                with self._task_lock:
                    self.metrics["last_latency"] = duration
                    outputs = max(int(self.metrics.get("outputs", 0)), 1)
                    prev_avg = float(self.metrics.get("avg_latency", 0.0))
                    self.metrics["avg_latency"] = prev_avg + ((duration - prev_avg) / outputs)
                if self.output_queue is not None:
                    try:
                        self.output_queue.put_nowait(payload)
                    except queue.Full:
                        self._emit("error", {"message": "output_queue_full"}, task_id=task_id)
                    else:
                        self._emit("output_ready", payload, task_id=task_id)
                else:
                    self._emit("output_ready", payload, task_id=task_id)
                self._publish_metrics()

        except Exception as exc:
            self._emit("error", {"message": str(exc)}, task_id=task_id)
        finally:
            if self._is_active(task_id, cancel_event):
                self._transition("idle", task_id=task_id)

    def handle_item(self, item: dict) -> None:
        task_id = self._next_task_id()
        cancel_event = threading.Event()
        self._set_active(task_id, cancel_event, None)
        self._process_item(item, task_id, cancel_event)

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
            if self._active_thread and self._active_thread.is_alive():
                if not self.cancel_on_new_input:
                    time.sleep(0.05)
                    continue
                try:
                    item = self.input_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                self._cancel_active("superseded")
                # latest-wins semantics: keep only the most recent pending item
                self._pending_item = item
                self._transition("listening")
                try:
                    # We do not rely on queue.join(); task_done is called immediately.
                    self.input_queue.task_done()
                except Exception:
                    pass
                continue

            if self._pending_item is not None:
                item = self._pending_item
                self._pending_item = None
            else:
                try:
                    item = self.input_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                try:
                    # We do not rely on queue.join(); task_done is called immediately.
                    self.input_queue.task_done()
                except Exception:
                    pass

            if self._cancel_grace_until:
                wait = self._cancel_grace_until - time.time()
                if wait > 0:
                    time.sleep(wait)
                self._cancel_grace_until = 0.0

            self._start_task(item)

    def stop(self) -> None:
        self.running = False
        if self._active_cancel:
            self._active_cancel.set()
