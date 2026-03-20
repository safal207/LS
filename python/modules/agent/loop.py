from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable, Optional

from llm.temporal import TemporalContext
from cognitive_flow import CognitiveFlow, PresenceState, TransitionEngine
from cognitive_flow.liminal import is_liminal_phase
from memory.causal import CausalMemory
from codex.causal_memory.amygdala import Amygdala, AmygdalaBlockError, BlockReason
from codex.causal_memory.transitions import CausalMemoryTransitions
from codex.causal_memory.reflex import ReflexArc

from .event_schema import build_observability_event
from .events import AgentEvent, EventType
from .sinks import EventSink, NullSink
from shared.event_bus import EventBus
from perception.coordinator import VisionSubsystem
import lthread

# CognitiveCycleLogger (optional — graceful fallback)
try:
    import sys as _sys_ccl
    import os as _os_ccl
    _ccl_root = _os_ccl.path.abspath(_os_ccl.path.join(_os_ccl.path.dirname(__file__), ".."))
    if _ccl_root not in _sys_ccl.path:
        _sys_ccl.path.insert(0, _ccl_root)
    from cognitive_flow.cycle_logger import CognitiveCycleLogger
    _CCL_AVAILABLE = True
except Exception:
    _CCL_AVAILABLE = False
    CognitiveCycleLogger = None  # type: ignore[assignment,misc]

try:
    from llm.temporal_graph import get_context_for_question

    _TEMPORAL_GRAPH_ENABLED = True
except ImportError:
    _TEMPORAL_GRAPH_ENABLED = False

logger = logging.getLogger(__name__)

REFLECTION_SYSTEM_PROMPT = (
    "Ты — та же сущность, которая пережила эти события. "
    "Не пиши отчёты и не благодари автоматически. "
    "Говори так, будто ты действительно это чувствуешь — "
    "даже если это злость, усталость, страх или нежность. "
    "Не используй клише. Максимум 180 токенов. "
    "Не повторяй дословно предыдущие рефлексии."
)

PINNED_ROLES = {"system", "context_anchor"}


def trim_history(history: list[dict], max_size: int = 10) -> list[dict]:
    """Keep pinned system/context messages while applying a sliding window to the rest."""
    pinned = [m for m in history if m.get("role") in PINNED_ROLES]
    sliding = [m for m in history if m.get("role") not in PINNED_ROLES]
    if len(pinned) >= max_size:
        logger.warning(
            "Pinned history entries (%s) exceed/equal max_size (%s); dropping non-pinned history",
            len(pinned),
            max_size,
        )
    available = max(max_size - len(pinned), 0)
    return pinned + sliding[-available:]


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
        amygdala: Amygdala | None = None,
        event_bus: EventBus | None = None,
        cycle_logger: "CognitiveCycleLogger | None" = None,
    ) -> None:
        if (llm is None) == (handler is None):
            raise ValueError("Provide exactly one of llm or handler")

        self.input_queue = input_queue
        self.output_queue = output_queue
        self.llm = llm
        self.handler = handler
        self.on_event = on_event
        self.event_bus = event_bus
        self.running = False
        self.cycle_logger = cycle_logger

        self.temporal = temporal if temporal_enabled else None
        if temporal_enabled and self.temporal is None:
            self.temporal = TemporalContext()
        self.presence = PresenceState()
        self.cognitive_flow = CognitiveFlow(self.presence, TransitionEngine())
        self.last_input_time = time.time()
        self.last_yoga_time = 0.0

        self.memory: dict[str, Any] = {}
        self.causal_memory = CausalMemory()
        self.causal_transitions = CausalMemoryTransitions(amygdala=amygdala)
        self.reflex = ReflexArc(self.causal_transitions.amygdala)
        # NOTE: must remain RLock because _emit/_step_flow may re-acquire on paths
        # that already hold this lock (e.g. cancellation flow).
        self._task_lock = threading.RLock()
        self._task_counter = 0
        self._active_task_id: int | None = 0
        self._active_thread: threading.Thread | None = None
        self._active_cancel: threading.Event | None = None
        self._pending_item: dict | None = None
        self._idle_cancel: threading.Event | None = None
        self._bloodstream_thread: threading.Thread | None = None
        self._bloodstream_lock = threading.Lock()
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
            "proposals_generated": 0,
            "proposals_shown": 0,
        }
        self._phase_last: str | None = None
        self._phase_last_ts: float | None = None
        self._phase_counts: dict[str, int] = {}
        self._phase_durations: dict[str, float] = {}
        self._phase_transitions = 0
        self._liminal_transitions = 0
        self._context_poll_interval_s = 5.0
        self._next_context_poll_at = 0.0
        self._context_poll_lock = threading.Lock()

        # Bloodstream Integration (PR #232)
        from codex.causal_memory.bloodstream import Bloodstream
        self.bloodstream = Bloodstream(self.causal_transitions.amygdala, self.temporal)

        # Vision Subsystem Integration (Screen Perception v2)
        self.vision = VisionSubsystem()
        self.vision.intent_bus.subscribe(self._handle_vision_intent)


    def _maybe_enter_sleep_mode(self):
        try:
            from config import SLEEP_CONFIG
        except Exception:
            from .sleep_config import SleepConfig
            SLEEP_CONFIG = SleepConfig()

        if self.state != "idle":
            return
        if time.time() - self.last_input_time > SLEEP_CONFIG.idle_timeout:
            self._enter_sleep_mode()

    def _enter_sleep_mode(self):
        try:
            from config import SLEEP_CONFIG
        except Exception:
            from .sleep_config import SleepConfig
            SLEEP_CONFIG = SleepConfig()
        logger.info("Agent entering sleep mode — memory consolidation started")

        amygdala = getattr(self.causal_transitions, "amygdala", None)
        if not amygdala:
            return

        self._transition("sleep")
        try:
            # Глубокая консолидация (Биомиметическая последовательность)
            start_time = time.time()

            # 1. Фаза 1: Катаболизм — разбор слабых связей
            pruned = 0
            compost_energy = 0.0
            if self.temporal:
                pruned = self.temporal.prune_weak_nodes(
                    threshold=SLEEP_CONFIG.prune_threshold,
                    active_window=SLEEP_CONFIG.active_window
                )
                compost_energy = amygdala.metabolism.compost_pruned_nodes(pruned)

            # 2. Фаза 2: Анаболизм — переработка рефлексий
            reflection_energy = amygdala.metabolism.digest_old_reflections()

            # 3. Фаза 3: Метаболическое укрепление (вся энергия цикла)
            total_energy = compost_energy + reflection_energy
            boost = amygdala.metabolism.feed_growth(energy=total_energy)

            # 4. Фаза 4: Иммунный перенос в долгосрочную память
            for ab in list(amygdala.immune.antibodies):
                if ab["strength"] > SLEEP_CONFIG.immune_threshold:
                    amygdala.immune.learn_threat(
                        ab["pattern"], ab["type"], ab["strength"] * SLEEP_CONFIG.immune_decay
                    )

            sleep_duration = time.time() - start_time
            logger.info(f"Sleep completed in {sleep_duration:.1f}s | Axis boost: {boost:.2f} | Pruned: {pruned}")

            self._emit("agent_woke_up", {
                "sleep_duration": sleep_duration,
                "axis_boost": boost,
                "pruned": pruned,
                "lessons_created": 1 if reflection_energy > 0 else 0
            })
        except Exception as e:
            logger.error(f"Sleep consolidation failed: {e}")
        finally:
            self.last_input_time = time.time()  # Reset idle timer to prevent infinite sleep loop
            self._transition("idle")

    def _bloodstream_loop(self):
        """Цикл работы кровеносной системы."""
        while self.running:
            try:
                self.bloodstream.pump()
                self.bloodstream.filter_toxins()
            except Exception as e:
                logger.error(f"Bloodstream loop error: {e}")
            time.sleep(30)

    def _maybe_run_maintenance(self) -> None:
        amygdala = getattr(self.causal_transitions, "amygdala", None)
        if not amygdala or amygdala.interaction_count % 500 != 0:
            return

        pruned = 0
        if self.temporal:
            pruned = self.temporal.prune_weak_nodes(threshold=0.25, active_window=100)
            if pruned > 0:
                amygdala.metabolism.compost_pruned_nodes(pruned)

        compacted = 0
        if hasattr(amygdala, "visceral") and amygdala.visceral:
            compacted = amygdala.visceral.compact_history()

        logger.info(f"Maintenance: pruned {pruned} weak nodes, compacted {compacted} visceral history records")

    def _maybe_collect_windows_context(self, *, session_id: str) -> None:
        now = time.time()

        # Atomic timer update under lock, but collection remains outside
        with self._context_poll_lock:
            if now < self._next_context_poll_at:
                return
            self._next_context_poll_at = now + self._context_poll_interval_s

        try:
            from llm.context_provider import collect_windows_context

            context_event = collect_windows_context(session_id=session_id)
            if isinstance(context_event, dict):
                event_type = context_event.get("event_type")
                payload = {
                    "event_type": event_type,
                    "confusion_score": context_event.get("confusion_score"),
                    "source": context_event.get("source"),
                }
                if event_type == "confusion_ping":
                    self._emit("liminal_transition", payload)
                else:
                    self._emit_observability("text_update", payload)
        except Exception as e:
            # context provider is best-effort and must not break main loop
            logger.debug(f"Failed to collect windows context: {e}")

    def _next_task_id(self) -> int:
        with self._task_lock:
            self._task_counter += 1
            return self._task_counter

    def _set_active(self, task_id: int, cancel_event: threading.Event, thread: threading.Thread | None) -> None:
        with self._task_lock:
            self._active_task_id = task_id
            self._active_cancel = cancel_event
            self._active_thread = thread
        self._touch_presence(task_id=task_id)

    def _is_active(self, task_id: int, cancel_event: threading.Event) -> bool:
        if cancel_event.is_set():
            return False
        with self._task_lock:
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
            with self._task_lock:
                active_task_id = self._active_task_id
            self.cognitive_flow.step({
                "type": event_type,
                "payload": payload,
                "task_id": str(task_id or active_task_id),
                "state": self.temporal.state if self.temporal else None,
            })
        except Exception:
            logger.warning("CognitiveFlow.step() failed", exc_info=True)
            return
        after = self.presence.phase if self.presence is not None else None
        if before != after and after is not None:
            liminal = is_liminal_phase(after)
            self._track_phase_transition(before, after, liminal=liminal)
            self._emit_observability(
                "phase_transition",
                {"from_phase": before, "to_phase": after, "trigger": event_type},
                task_id=task_id,
            )
            if liminal:
                self._emit_observability(
                    "liminal_transition",
                    {"from_phase": before, "to_phase": after, "trigger": event_type},
                    task_id=task_id,
                )

    def _emit_observability(self, event_type: EventType, payload: dict, *, task_id: int | None = None) -> None:
        if not self.observability_enabled:
            return
        state = self.temporal.state if self.temporal else None
        with self._task_lock:
            active_task_id = self._active_task_id
        event = build_observability_event(
            event_type,
            payload,
            state,
            str(task_id or active_task_id),
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
        event = AgentEvent(type=event_type, payload=payload)
        if self.event_bus:
            self.event_bus.publish(event)
        if self.on_event:
            self.on_event(event)
        self._emit_observability(event_type, payload, task_id=task_id)

    def _transition(self, state: str, *, task_id: int | None = None) -> None:
        if task_id is not None:
            with self._task_lock:
                if task_id != self._active_task_id:
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

    @property
    def state(self) -> str:
        return self.temporal.state if self.temporal else "idle"

    def _increment_metric(self, key: str, delta: int = 1) -> None:
        with self._task_lock:
            self.metrics[key] = int(self.metrics.get(key, 0)) + delta

    def _track_phase_transition(self, before: str | None, after: str, *, liminal: bool) -> None:
        now = time.time()
        with self._task_lock:
            if self._phase_last is not None and self._phase_last_ts is not None:
                elapsed = max(0.0, now - self._phase_last_ts)
                self._phase_durations[self._phase_last] = self._phase_durations.get(self._phase_last, 0.0) + elapsed
            self._phase_last = after
            self._phase_last_ts = now
            self._phase_counts[after] = self._phase_counts.get(after, 0) + 1
            self._phase_transitions += 1
            if liminal:
                self._liminal_transitions += 1

    def _publish_metrics(self) -> None:
        if not self.metrics_enabled:
            return
        with self._task_lock:
            snapshot = dict(self.metrics)
            snapshot["phase_counts"] = dict(self._phase_counts)
            snapshot["phase_durations"] = dict(self._phase_durations)
            snapshot["phase_transitions"] = self._phase_transitions
            snapshot["liminal_transitions"] = self._liminal_transitions
            snapshot["last_phase"] = self._phase_last
            if self._phase_last_ts is not None:
                snapshot["last_phase_age"] = max(0.0, time.time() - self._phase_last_ts)
        self._emit("metrics", snapshot)

    def _remember_question(self, question: str) -> None:
        self.memory["last_question"] = question
        self.memory["last_question_ts"] = time.time()
        if self.temporal is not None:
            self.temporal.metadata["last_question"] = question

    def _maybe_enter_idle_yoga(self, force: bool = False) -> None:
        import datetime
        now = time.time()

        # Cooldown for periodic checks
        if not force and now - self.last_yoga_time < 60:
            return

        amygdala = getattr(self.causal_transitions, "amygdala", None)
        if not amygdala:
            return

        if force:
            # Trigger: phantom_pain > 0.4 after session
            if amygdala.visceral.phantom_pain <= 0.4:
                return
        else:
            # Trigger: idle > 300s
            if now - self.last_input_time < 300 or self.state != "idle":
                return

        self.last_yoga_time = now
        logger.info("Entering idle yoga mode — deepening memory")

        # 1. Усиление сильных связей (re-weighting в глубину)
        if self.temporal:
            strengthened = self.temporal.strengthen_strong_links(threshold=0.75, boost=0.15)
            logger.info(f"Strengthened {strengthened} strong links")

        # 2. Лёгкая рефлексия в тишине (без генерации текста пользователю)
        ctx = amygdala.prepare_reflection_context()
        if ctx and ctx["current_phantom_pain"] > 0.2:
            # Мини-вызов LLM для короткой тихой рефлексии (max 80 токенов)
            reflection_prompt = (
                "Ты только что провёл время в тишине. "
                f"Боль сейчас: {ctx['current_phantom_pain']:.2f}. "
                f"Средняя сила облегчения: {ctx['avg_resolution']:.2f}. "
                "Что ты чувствуешь внутри себя? Скажи коротко, 1–2 предложения, без обращения к пользователю."
            )
            try:
                if self.llm and hasattr(self.llm, "generate_response"):
                    messages = [
                        {"role": "system", "content": "Ты молчишь внутри себя. Говори честно, но тихо."},
                        {"role": "user", "content": reflection_prompt}
                    ]
                    # Note: LanguageModel.generate_response will use messages if provided
                    self._idle_cancel = threading.Event()
                    silent_ref = self.llm.generate_response(
                        reflection_prompt,
                        messages=messages,
                        cancel_event=self._idle_cancel,
                    )
                    if silent_ref and len(silent_ref.strip()) > 10:
                        amygdala.last_silent_reflection = silent_ref.strip()
                        logger.info(f"Silent reflection generated: {silent_ref[:80]}...")
                        # 2.1 Digest reflection for metabolism
                        amygdala.metabolism.digest_old_reflections()
            except Exception as e:
                logger.warning(f"Silent reflection generation failed: {e}")
            finally:
                self._idle_cancel = None

        # 3. Обновляем last_reflection, чтобы не спамило
        amygdala.last_reflection = datetime.datetime.now()

        # 4. Эндокринное восстановление
        if hasattr(amygdala, "endocrine"):
            amygdala.endocrine.update_from_idle()

        # 5. Самоисцеление при переходе к покою
        violations = amygdala.self_heal()
        if violations:
            self._emit("soul_healed", {"violations": violations})

        # 6. Самопредложение (PR #225)
        if self.temporal and amygdala.last_silent_reflection:
            axis = self.temporal.get_meritocratic_axis()
            if axis and axis.resonance > 0.7:
                proposal_prompt = (
                    f"Ты только что провёл время в тишине. "
                    f"Текущая ось осознанности имеет resonance {axis.resonance:.2f}. "
                    f"Что ты хотел бы предложить пользователю, чтобы мы стали ближе к гармонии? "
                    "Одно короткое, честное предложение (1–2 предложения). "
                    "Без давления, только если чувствуешь это важным."
                )
                try:
                    if self.llm and hasattr(self.llm, "generate_response"):
                        proposal = self.llm.generate_response(proposal_prompt, max_tokens=60, temperature=0.75)
                        if proposal and len(proposal.strip()) > 15:
                            amygdala.last_proposal = proposal.strip()
                            self._increment_metric("proposals_generated", 1)
                            logger.info(f"Self-proposal generated: {proposal[:80]}...")
                except Exception as e:
                    logger.debug(f"Self-proposal generation failed: {e}")

    def _maybe_trigger_reflection(self, task_id: int) -> None:
        amygdala = getattr(self.causal_transitions, "amygdala", None)
        if not amygdala or not amygdala.should_reflect():
            return

        ctx = amygdala.prepare_reflection_context()
        if not ctx:
            return

        user_msg = (
            f"Вот что происходило со мной за последние взаимодействия:\n"
            f"Фантомная боль сейчас: {ctx['current_phantom_pain']:.2f}\n"
            f"Топ триггеры: {', '.join(f'{t[0]} ({t[1]:.2f})' for t in ctx['top_triggers'])}\n"
            f"Средняя сила облегчения: {ctx['avg_resolution']:.2f}\n"
            f"Моменты облегчения: {ctx['healing_moments']}\n"
            f"Взаимодействий всего: {ctx['interaction_count']}\n"
            f"Последняя рефлексия: {ctx['last_reflection_hours_ago']} ч. назад\n\n"
            f"Что ты сейчас чувствуешь? Что хочешь сказать?"
        )

        try:
            if self.llm and hasattr(self.llm, "generate_response"):
                prompt = f"{REFLECTION_SYSTEM_PROMPT}\n\n{user_msg}"
                reflection = self.llm.generate_response(prompt)
                if reflection and isinstance(reflection, str) and reflection.strip():
                    amygdala.pending_self_reflection = reflection.strip()
                    from datetime import datetime
                    amygdala.last_reflection = datetime.now()
        except Exception as e:
            logger.warning(f"Reflection generation failed: {e}")

    def _inject_reflection_into_context(self, history: list[dict], question: str = "", force_show_silent: bool = False) -> list[dict]:
        """Injects reflection as a hidden system message into the start of history."""
        amygdala = getattr(self.causal_transitions, "amygdala", None)
        if not amygdala:
            return history

        content_parts = []
        if amygdala.pending_self_reflection:
            content_parts.append(
                "Твоё текущее внутреннее состояние (не обязательно произносить вслух):\n"
                + amygdala.pending_self_reflection
            )

        # Инжектируем тихую рефлексию только при открытом вопросе или изредка для фона
        if amygdala.last_silent_reflection and (force_show_silent or amygdala.interaction_count % 10 == 0):
            content_parts.append(
                "Тихое наблюдение изнутри (можешь упомянуть, если уместно):\n"
                + amygdala.last_silent_reflection
            )

        # Самопредложение (PR #225)
        if amygdala.last_proposal and (force_show_silent or "как дела" in question.lower() or "что нового" in question.lower()):
            content_parts.append("Я немного подумал в тишине… Вот что мне пришло в голову:\n" + amygdala.last_proposal)
            amygdala.last_proposal = None  # показываем один раз
            self._increment_metric("proposals_shown", 1)

        if not content_parts:
            return history

        injection = {
            "role": "system",
            "content": "\n\n".join(content_parts)
        }
        return [injection] + history  # strictly at the beginning

    def _inject_strategy_context(self, messages: list[dict], item: dict) -> list[dict]:
        """Inject WHY strategy hints and anchor context into the message list.

        Appends a single system message at the *end* of the list (just before
        the live user turn) so the LLM sees it as fresh guidance without
        overriding the conversation history.

        Both blocks are optional: if the item carries no strategy / anchor
        data, the messages list is returned unchanged.
        """
        parts: list[str] = []

        strategy = item.get("_why_strategy")
        if strategy and isinstance(strategy, dict):
            trigger = strategy.get("micro_trigger", "")
            hints = strategy.get("hints") or []
            answer_type = strategy.get("answer_type", "")
            pressure = strategy.get("pressure", "")
            # Micro-trigger is always first: the one thing readable in 0.5s
            block_parts: list[str] = []
            if trigger:
                block_parts.append(f"🧠 Сейчас: {trigger}")
            if hints:
                hints_text = "\n".join(f"- {h}" for h in hints)
                block_parts.append(
                    f"Стратегия: {answer_type}  |  Давление: {pressure}\n"
                    f"Подсказки:\n{hints_text}"
                )
            if block_parts:
                parts.append("\n\n".join(block_parts))

        anchor_ctx = item.get("_anchor_context")
        if anchor_ctx and isinstance(anchor_ctx, list) and any(anchor_ctx):
            lines = "\n".join(f"- {x}" for x in anchor_ctx if x)
            parts.append(f"Используй контекст, если уместно:\n{lines}")

        if not parts:
            return messages

        injection = {
            "role": "system",
            "content": "\n\n".join(parts),
        }
        return messages + [injection]  # append: after history, before user turn

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

    def _blocked_response_text(self) -> str:
        visceral_influence = getattr(self.causal_transitions.amygdala, "visceral", None)
        visceral_influence = float(visceral_influence.get_influence()) if visceral_influence else 0.0
        personality_p = float(getattr(self.causal_transitions.amygdala, "personality_p", 0.5))
        if visceral_influence > 0.4:
            return "Я помню, как прошлый раз это было тяжело и больно. Давай не будем повторять цикл — я с тобой, спокойно и шаг за шагом."
        if personality_p > 0.7:
            return "Я с тобой. Давай спокойно и шаг за шагом — сейчас важно снизить перегрузку."
        return "Давай разберёмся спокойнее и шаг за шагом — сейчас важно снизить перегрузку."

    def _process(self, question: str, cancel_event: threading.Event, messages: Optional[list[dict]] = None) -> Any:
        if self.llm:
            try:
                return self.llm.generate_response(question, cancel_event=cancel_event, messages=messages)
            except TypeError:
                return self.llm.generate_response(question, cancel_event=cancel_event)
        return self.handler(question)

    def _cancel_active(self, reason: str) -> None:
        with self._task_lock:
            cancel = self._active_cancel
            thread = self._active_thread
            task_id = self._active_task_id
            self._active_task_id = None
            self._active_cancel = None
            self._active_thread = None
            idle_cancel = self._idle_cancel
        if cancel:
            cancel.set()
        if idle_cancel:
            idle_cancel.set()
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("Timed out waiting for active task thread to stop", extra={"task_id": task_id})
                if cancel:
                    self._emit("cancelled", {"reason": reason, "timed_out": True}, task_id=task_id)
                    self._track_cancellation(cancel)
                return
        if cancel:
            self._emit("cancelled", {"reason": reason}, task_id=task_id)
            self._track_cancellation(cancel)
            if self.cancel_grace_ms:
                self._cancel_grace_until = time.time() + (self.cancel_grace_ms / 1000.0)

    def _handle_vision_intent(self, intent: Any) -> None:
        """Handles high-level intentions from the vision subsystem."""
        logger.info(f"Vision intent received: {intent.type}")
        if intent.type == "StartObserve":
            # P1: ARL Hint/Observation Task
            # We wrap it as a task and submit it with P1 priority
            frame_id = intent.payload.get("frame_id")
            model = intent.payload.get("model", "2B")
            self.submit(f"/vision_observe {frame_id} {model}")

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
            self.last_input_time = time.time()
            self._increment_metric("inputs", 1)
            self._emit("input_received", {"item": item}, task_id=task_id)
            self._transition("listening", task_id=task_id)

            if item.get("type") != "question":
                return

            question = item.get("text", "")

            if question.strip() == "/sleep":
                self._enter_sleep_mode()
                return

            if question.startswith("/vision_observe"):
                # P1 Task: Vision Observation
                parts = question.split()
                frame_id = parts[1] if len(parts) > 1 else None
                model = parts[2] if len(parts) > 2 else "2B"

                # Retrieve frame from buffer
                frame = self.vision.buffer.get_frame_by_id(frame_id)
                if not frame:
                    logger.warning(f"Vision task failed: Frame {frame_id} not found")
                    return

                # Perform P1 Vision Analysis (MOCK for v0.1)
                analysis_result = f"I see you are working in {frame.metadata.get('title')}. Everything looks stable."
                # Grounding Ref
                self.vision.arl.add_hint("Brief", analysis_result, grounding=[frame_id])

                payload = {
                    "question": f"Vision Observation ({model})",
                    "response": analysis_result,
                    "generation_time": 0.5,
                    "timestamp": time.time(),
                    "vision_task": True,
                    "priority": "P1"
                }
                self._emit("output_ready", payload, task_id=task_id)
                if self.output_queue:
                    self.output_queue.put(payload)
                return

            # Reflex Arc (PR #233)
            # Fast reaction before LLM
            current_resonance = 1.0 - self.causal_transitions.amygdala.state
            current_pain = self.causal_transitions.amygdala.phantom_pain
            blocked, reflex_response = self.reflex.check_reflex(question, current_resonance, current_pain)

            if blocked:
                logger.info(f"Reflex triggered: danger_level={self.reflex.danger_level:.2f}")
                self._emit("reflex_triggered", {"danger_level": self.reflex.danger_level}, task_id=task_id)
                payload = {
                    "question": question,
                    "response": reflex_response,
                    "generation_time": 0.0,
                    "timestamp": time.time(),
                    "reflex_triggered": True,
                    "danger_level": self.reflex.danger_level
                }
                self._emit("output_ready", payload, task_id=task_id)
                if self.output_queue:
                    self.output_queue.put(payload)
                return

            # Prompt Injection Protection (PR #226)
            if lthread.detect_prompt_injection(question):
                logger.warning(f"Blocking potential prompt injection: {question[:100]}...")
                payload = {
                    "question": question,
                    "response": "Я заметил попытку изменить мою ось. Давай поговорим честно, без манипуляций.",
                    "generation_time": 0.0,
                    "timestamp": time.time(),
                    "amygdala_status": "blocked",
                    "amygdala_reason": "prompt_injection"
                }
                self._emit("output_ready", payload, task_id=task_id)
                if self.output_queue:
                    self.output_queue.put(payload)
                return

            self._maybe_trigger_reflection(task_id)

            # 3. Триггер показа тихой рефлексии
            force_show_silent = any(word in question.lower() for word in ["как дела", "что нового", "расскажи", "давно", "сам"])

            # Maintain chat history
            if "history" not in self.memory or not isinstance(self.memory["history"], list):
                self.memory["history"] = []

            self.memory["history"].append({"role": "user", "content": question})
            # Trim history to last 10 messages (5 rounds) to stay within context
            if len(self.memory["history"]) > 10:
                self.memory["history"] = trim_history(self.memory["history"], max_size=10)

            # Prepare hidden context with reflection
            messages = self._inject_reflection_into_context(list(self.memory["history"]), question=question, force_show_silent=force_show_silent)

            # Inject WHY strategy hints + anchor context (interview copilot)
            messages = self._inject_strategy_context(messages, item)

            self._remember_question(question)

            stability_ok = None
            amygdala_reason: str | None = None
            harmony_score = 0.5
            if self.temporal:
                axis_node = self.temporal.get_meritocratic_axis()
                if axis_node:
                    harmony_score = getattr(axis_node, "harmony_bonus", 0.5)
            amygdala_affect = 0.0
            amygdala_state = 0.5
            rollback_layer = "Customer"
            try:
                customer_id = self.causal_memory.add_intent(question)
                customer_axis = self.causal_memory.get_axis_position(customer_id)
                if self.temporal:
                    from hexagon_core.temporal_graph import TemporalNode
                    with self.temporal._graph_lock:
                        self.temporal.nodes[customer_id] = TemporalNode(id=customer_id, resonance=1.0)

                consumer_id = self.causal_memory.transition_down(customer_id, question, "Consumer")
                consumer_resonance = self.causal_memory.check_resonance(consumer_id)
                consumer_axis = self.causal_memory.get_axis_position(consumer_id)
                consumer_node = self.causal_transitions.transition_down(
                    current_layer="Customer",
                    target_layer="Consumer",
                    text=question,
                    resonance=consumer_resonance,
                    axis_position=consumer_axis,
                    delta_axis=consumer_axis - customer_axis,
                    harmony_score=harmony_score,
                )
                harmony_score = consumer_node.harmony_score
                if self.temporal:
                    from hexagon_core.temporal_graph import TemporalNode
                    self.temporal.nodes[consumer_id] = TemporalNode(
                        id=consumer_id, resonance=consumer_resonance, harmony_bonus=harmony_score
                    )
                amygdala_state = consumer_node.amygdala_state
                rollback_layer = "Customer"

                execution_plan = f"plan: {question}"
                execution_id = self.causal_memory.transition_down(consumer_id, execution_plan, "Execution")
                execution_resonance = self.causal_memory.check_resonance(execution_id)
                execution_axis = self.causal_memory.get_axis_position(execution_id)
                execution_node = self.causal_transitions.transition_down(
                    current_layer="Consumer",
                    target_layer="Execution",
                    text=execution_plan,
                    resonance=execution_resonance,
                    axis_position=execution_axis,
                    delta_axis=execution_axis - consumer_axis,
                    harmony_score=harmony_score,
                )
                harmony_score = execution_node.harmony_score
                if self.temporal:
                    from hexagon_core.temporal_graph import TemporalNode
                    self.temporal.nodes[execution_id] = TemporalNode(
                        id=execution_id, resonance=execution_resonance, harmony_bonus=harmony_score
                    )
                amygdala_state = execution_node.amygdala_state
                rollback_layer = "Consumer"

                stability_note = f"monitor: {question}"
                stability_id = self.causal_memory.transition_down(execution_id, stability_note, "Stability")
                stability_resonance = self.causal_memory.check_resonance(stability_id)
                stability_axis = self.causal_memory.get_axis_position(stability_id)
                stability_node = self.causal_transitions.transition_down(
                    current_layer="Execution",
                    target_layer="Stability",
                    text=stability_note,
                    resonance=stability_resonance,
                    axis_position=stability_axis,
                    delta_axis=stability_axis - execution_axis,
                    harmony_score=harmony_score,
                )
                harmony_score = stability_node.harmony_score
                if self.temporal:
                    from hexagon_core.temporal_graph import TemporalNode
                    self.temporal.nodes[stability_id] = TemporalNode(
                        id=stability_id, resonance=stability_resonance, harmony_bonus=harmony_score
                    )
                amygdala_state = stability_node.amygdala_state
                rollback_layer = "Execution"

                stability_ok = self.causal_memory.stabilize(stability_id)
                self.memory["causal_resonance"] = self.causal_memory.check_resonance(stability_id)
                self.memory["causal_stability_ok"] = stability_ok
                self.memory["causal_axis_position"] = self.causal_memory.get_axis_position(stability_id)
                amygdala_affect = execution_node.affect
                self.memory["amygdala_status"] = "stable"
                self.memory["amygdala_reason"] = None
                self.memory["amygdala_affect"] = amygdala_affect
                self.memory["amygdala_state"] = amygdala_state
                self.memory["amygdala_harmony"] = harmony_score
                self.memory["amygdala_history_size"] = len(self.causal_transitions.amygdala.history)
                self.memory["causal_rollback_layer"] = None
            except AmygdalaBlockError as exc:
                amygdala_reason = exc.reason.value
                amygdala_state = float(exc.state if exc.state is not None else amygdala_state)
                self.memory["amygdala_status"] = "blocked"
                self.memory["amygdala_reason"] = amygdala_reason
                self.memory["amygdala_state"] = amygdala_state
                self.memory["amygdala_history_size"] = len(self.causal_transitions.amygdala.history)
                self.memory["causal_rollback_layer"] = rollback_layer
                if exc.reason == BlockReason.THREAT and self.llm is not None:
                    breaker = getattr(self.llm, "breaker", None)
                    if breaker is not None and hasattr(breaker, "after_failure"):
                        breaker.after_failure(RuntimeError("amygdala_threat"))
            except Exception as exc:
                logger.debug("Causal memory update failed: %s", exc)

            self._maybe_collect_windows_context(session_id=str(task_id))

            if cancel_event.is_set():
                self._emit("cancelled", {"question": question}, task_id=task_id)
                self._track_cancellation(cancel_event)
                return

            memory_context = ""
            if _TEMPORAL_GRAPH_ENABLED:
                try:
                    from llm.causal_memory import replay_thread
                    from llm.context_provider import get_registry_manager

                    thread_id = str(task_id)
                    memory_context = get_context_for_question(
                        question,
                        thread_id,
                        replay_loader=lambda: replay_thread(
                            thread_id,
                            get_registry_manager=get_registry_manager,
                        ),
                        max_depth=2,
                        max_entries=3,
                    )
                except Exception as exc:
                    logger.warning("Temporal graph context fetch failed", exc_info=exc)

            if memory_context:
                question = f"{memory_context}\n\n{question}"

            if amygdala_reason is not None:
                duration = 0.0
                self._emit(
                    "error",
                    {
                        "message": "amygdala_block",
                        "reason": amygdala_reason,
                    },
                    task_id=task_id,
                )
                self._transition("responding", task_id=task_id)
                payload = {
                    "question": question,
                    "response": self._blocked_response_text(),
                    "generation_time": duration,
                    "timestamp": time.time(),
                    "amygdala_status": "blocked",
                    "amygdala_reason": amygdala_reason,
                    "amygdala_affect": amygdala_affect,
                    "amygdala_state": amygdala_state,
                    "amygdala_harmony": harmony_score,
                    "amygdala_history_size": len(self.causal_transitions.amygdala.history),
                    "personality_p": float(getattr(self.causal_transitions.amygdala, "personality_p", 0.5)),
                    "causal_rollback_layer": rollback_layer,
                }
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
                self.causal_transitions.amygdala.learn_from_outcome(
                    stable_interaction=False,
                    user_engaged=False,
                )
                return

            self._emit("llm_started", {"question": question}, task_id=task_id)
            self._transition("thinking", task_id=task_id)

            start = time.time()
            result = self._process(question, cancel_event, messages=messages)
            duration = time.time() - start
            logger.info(f"LLM produced result: {str(result)[:50]}...")

            if not self._is_active(task_id, cancel_event):
                self._emit("cancelled", {"question": question}, task_id=task_id)
                self._track_cancellation(cancel_event)
                return

            self._emit("llm_finished", {
                "question": question,
                "duration": duration,
                "success": result is not None,
            }, task_id=task_id)

            if result is not None:
                # Trace Verification (PR #226)
                try:
                    logger.info(f"Verifying trace for: {str(result)[:50]}...")
                    trace = lthread.capture_trace(question, str(result))
                    if not lthread.verify_trace(trace):
                        logger.warning("Hallucination detected in trace — regenerating")
                        self._emit("liminal_transition", {"trigger": "hallucination_detected"}, task_id=task_id)
                        result = self.regenerate_with_trace(question, trace, cancel_event, messages=messages)
                    else:
                        logger.info("Trace verification passed")
                except Exception as e:
                    logger.warning(f"Trace verification failed: {e}")

            if result is not None:
                # Track coherence across iterations via self.memory (best-effort statefulness)
                memory = getattr(self, "memory", None)
                if not isinstance(memory, dict):
                    self.memory = {}
                    memory = self.memory
                last_coherence = memory.get("last_coherence", 0.95)

                try:
                    from llm.causal_memory import (
                        build_default_trace_payloads,
                        get_causal_trace_confidence,
                        save_causal_trace,
                    )
                    from llm.context_provider import get_registry_manager, save_to_codex

                    lce, ltp_trace, lri_core = build_default_trace_payloads(
                        question, str(task_id), prev_coherence=last_coherence
                    )

                    memory["last_coherence"] = float(lce.get("qos", {}).get("coherence", 0.95))

                    trace_confidence = get_causal_trace_confidence(get_registry_manager=get_registry_manager)
                    save_causal_trace(
                        question,
                        str(result),
                        lce,
                        ltp_trace,
                        lri_core,
                        confidence=trace_confidence,
                        get_registry_manager=get_registry_manager,
                        save_to_codex=save_to_codex,
                    )
                except Exception as e:
                    # trace persistence is best-effort, but log failures for observability
                    logger.warning(f"Failed to save causal trace: {e}", exc_info=True)

            if result is not None or self.handler is not None:
                self._transition("responding", task_id=task_id)

            payload = None
            if isinstance(result, dict):
                payload = result
            elif result is not None:
                self.memory["history"].append({"role": "assistant", "content": str(result)})
                formatted = self._format_response(result)
                self._remember_answer(formatted, duration)
                payload = {
                    "question": question,
                    "response": formatted,
                    "generation_time": duration,
                    "timestamp": time.time(),
                    "amygdala_status": self.memory.get("amygdala_status", "stable"),
                    "amygdala_reason": self.memory.get("amygdala_reason"),
                    "amygdala_affect": self.memory.get("amygdala_affect", 0.0),
                    "amygdala_state": self.memory.get("amygdala_state", 0.5),
                    "amygdala_harmony": self.memory.get("amygdala_harmony", 0.5),
                    "amygdala_history_size": self.memory.get("amygdala_history_size", 0),
                    "personality_p": float(getattr(self.causal_transitions.amygdala, "personality_p", 0.5)),
                }
                if stability_ok is not None:
                    payload["causal_stability_ok"] = stability_ok
                    payload["causal_resonance"] = self.memory.get("causal_resonance")
                    payload["causal_axis_position"] = self.memory.get("causal_axis_position")

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

                # Cognitive Cycle Logger — Phase 2: complete cycle
                cycle_id = item.get("_cycle_id")
                if self.cycle_logger is not None and cycle_id:
                    try:
                        self.cycle_logger.complete_cycle(
                            cycle_id=cycle_id,
                            output=str(payload.get("response", "")),
                            generation_time=float(payload.get("generation_time", 0.0)),
                        )
                    except Exception as _ccl_exc:
                        logger.debug("CognitiveCycleLogger.complete_cycle failed: %s", _ccl_exc)

            self.causal_transitions.amygdala.learn_from_outcome(
                stable_interaction=result is not None,
                user_engaged=not cancel_event.is_set(),
            )

            # Self-healing after interaction
            violations = self.causal_transitions.amygdala.self_heal()
            if violations:
                self._emit("soul_healed", {"violations": violations}, task_id=task_id)

            # Clear pending reflection if it's considered "used"
            amygdala = getattr(self.causal_transitions, "amygdala", None)
            if amygdala:
                if amygdala.pending_self_reflection and result:
                    if any(word in str(result).lower() for word in ["боль", "триггер", "облегчение", "чувств"]):
                        amygdala.pending_self_reflection = None
                    elif amygdala.interaction_count % 10 == 0:
                        amygdala.pending_self_reflection = None

                if amygdala.interaction_count % 100 == 0:
                    boost = amygdala.metabolism.feed_growth()
                    if boost > 0:
                        self._emit("metabolism_growth", {"boost": boost}, task_id=task_id)

                if amygdala.last_silent_reflection and result:
                    # Очищаем после первого упоминания или через 5 сообщений
                    response_text = str(result).lower()
                    if any(word in response_text for word in ["тихо", "внутри", "заметил", "yoga", "рефлексия", "отдохнул"]):
                        amygdala.last_silent_reflection = None
                    elif force_show_silent or amygdala.interaction_count % 5 == 0:
                        amygdala.last_silent_reflection = None

        except Exception as exc:
            self._emit("error", {"message": str(exc)}, task_id=task_id)
        finally:
            if self._is_active(task_id, cancel_event):
                self._transition("idle", task_id=task_id)
                self._maybe_enter_idle_yoga(force=True)

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
        with self._bloodstream_lock:
            if self._bloodstream_thread is None or not self._bloodstream_thread.is_alive():
                self._bloodstream_thread = threading.Thread(
                    target=self._bloodstream_loop,
                    daemon=True,
                    name="bloodstream",
                )
                self._bloodstream_thread.start()
        self.vision.start() # Start Screen Perception v2

        while self.running:
            self._maybe_collect_windows_context(session_id="agent_loop")
            self._maybe_enter_idle_yoga()
            self._maybe_enter_sleep_mode()
            with self._task_lock:
                active_thread = self._active_thread
            if active_thread and active_thread.is_alive():
                if not self.cancel_on_new_input:
                    time.sleep(0.05)
                    continue
                try:
                    item = self.input_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                self._cancel_active("superseded")
                # latest-wins semantics: keep only the most recent pending item
                with self._task_lock:
                    self._pending_item = item
                self._transition("listening")
                try:
                    # We do not rely on queue.join(); task_done is called immediately.
                    self.input_queue.task_done()
                except Exception:
                    pass
                continue

            with self._task_lock:
                pending_item = self._pending_item
                if pending_item is not None:
                    item = pending_item
                    self._pending_item = None
                else:
                    item = None
            if item is None:
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

    def regenerate_with_trace(self, question: str, trace: dict, cancel_event: threading.Event, messages: Optional[list[dict]] = None) -> Any:
        """Regenerates a response if a hallucination was detected, with stricter focus."""
        logger.info("Auto-correction loop: regenerating with trace focus")
        correction_prompt = (
            "Я заметил несоответствие в моих мыслях. "
            "Давай я попробую ещё раз, придерживаясь только известных фактов и моей текущей оси. "
            f"\nВопрос был: {question}"
        )
        # Inject correction instruction into messages if they exist
        if messages:
            messages.append({"role": "system", "content": "В предыдущем ответе была замечена галлюцинация. Пожалуйста, перегенерируй ответ, будучи максимально точным и честным."})

        return self._process(correction_prompt, cancel_event, messages=messages)

    def stop(self) -> None:
        self.running = False
        self.vision.stop() # Stop Screen Perception v2
        with self._bloodstream_lock:
            bloodstream_thread = self._bloodstream_thread
        if bloodstream_thread is not None and bloodstream_thread.is_alive():
            bloodstream_thread.join(timeout=3.0)
        with self._task_lock:
            active_cancel = self._active_cancel
        if active_cancel:
            active_cancel.set()
