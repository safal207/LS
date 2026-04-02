from PyQt6.QtWidgets import QApplication
import logging
import sys

from python.modules.shared.bootstrap import bootstrap_app

ctx = bootstrap_app(__file__, "ghostgpt")
cfg = ctx.config

import keyboard
from GhostGPT.modules.gui import GhostWindow
from GhostGPT.modules.audio import AudioWorker
from GhostGPT.modules.access_protocol import AccessProtocol
from modules.agent.loop import AgentLoop
from modules.agent.sinks import build_event_sink
from modules.agent.events import AgentEvent
from modules import config
from codex.causal_memory.amygdala import Amygdala
from agent.decision_pipeline import DecisionPipeline


logger = logging.getLogger(__name__)


class GhostGPT:
    def _on_reflex_triggered(self, _event: AgentEvent):
        self.window.trigger_reflex_warning()

    def _on_metabolism_growth(self, _event: AgentEvent):
        self.window.trigger_growth_animation()

    def _on_agent_woke_up(self, event: AgentEvent):
        self.window.trigger_wake_up_animation(event.payload)

    def _on_state_change(self, event: AgentEvent):
        if event.payload.get("state") == "sleep":
            self.window.trigger_sleep_animation()

    def _on_output_ready(self, _event: AgentEvent):
        snapshot = getattr(self.agent_loop.causal_transitions.amygdala, "last_snapshot", None) if self.agent_loop else None
        if isinstance(snapshot, dict):
            self.window.update_amygdala_visual(snapshot)

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = GhostWindow()
        self.audio = AudioWorker()
        self.decision_pipeline = DecisionPipeline({"action_history": [], "strategy_stats": {}, "action_log": []})
        self.window.set_decision_pipeline(self.decision_pipeline)
        ctx.services.register("logger", logger)

        # Initialize Access Protocol
        self.protocol = AccessProtocol(self.window, self.audio)

        # Connect signals
        event_sink = None
        if config.AGENT_OBSERVABILITY_ENABLED:
            event_sink = build_event_sink(config.AGENT_EVENT_SINK)

        self.agent_loop = AgentLoop(
            handler=self.protocol.execute_cycle,
            temporal_enabled=config.TEMPORAL_ENABLED,
            cancel_on_new_input=config.AGENT_CANCEL_ON_NEW_INPUT,
            cancel_grace_ms=config.AGENT_CANCEL_GRACE_MS,
            memory_max_chars=config.AGENT_MEMORY_MAX_CHARS,
            metrics_enabled=config.AGENT_METRICS_ENABLED,
            observability_enabled=config.AGENT_OBSERVABILITY_ENABLED,
            event_sink=event_sink,
            event_bus=ctx.event_bus,
            amygdala=Amygdala(user_id=self.window.current_user_id, persist_state=True),
        ) if config.AGENT_ENABLED else None
        if self.agent_loop:
            self.window.agent_loop = self.agent_loop
            ctx.services.register("memory", self.agent_loop.causal_memory)
            ctx.services.register("llm", self.protocol)
            ctx.event_bus.subscribe("reflex_triggered", self._on_reflex_triggered)
            ctx.event_bus.subscribe("metabolism_growth", self._on_metabolism_growth)
            ctx.event_bus.subscribe("agent_woke_up", self._on_agent_woke_up)
            ctx.event_bus.subscribe("state_change", self._on_state_change)
            ctx.event_bus.subscribe("output_ready", self._on_output_ready)
            self.audio.text_ready.connect(self.agent_loop.handle_input)
        else:
            self.audio.text_ready.connect(self.protocol.execute_cycle)
        self.audio.status_update.connect(self.window.update_status)

        # Hotkey setup (may be unavailable in headless/Linux containers)
        try:
            keyboard.add_hotkey(config.KEY_HIDE, self.toggle_visibility)
            keyboard.add_hotkey(config.KEY_LRI_HR, lambda: self.set_lri_mode("HR"))
            keyboard.add_hotkey(config.KEY_LRI_DEV, lambda: self.set_lri_mode("TECH"))
            keyboard.add_hotkey(config.KEY_LRI_CTO, lambda: self.set_lri_mode("CTO"))
        except Exception as exc:
            self.window.update_status(f"Hotkeys unavailable: {exc}")

    def set_lri_mode(self, mode):
        if self.protocol.capu.lri.set_mode(mode):
            self.window.update_status(f"Mode: {mode}")

    def toggle_visibility(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()

    def _build_reflection_dashboard(self):
        # BUG-19 fix: use decision_pipeline (which is defined in __init__)
        # instead of self.reflection_pipeline which never existed.
        from apps.ghostgpt.reflection_dashboard import ReflectionDashboard
        return ReflectionDashboard(self.decision_pipeline)

    def run(self):
        self.window.show()
        self.audio.start()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    ghost = GhostGPT()
    ghost.run()
