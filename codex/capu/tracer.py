from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .hooks import LLMHooks, STTHooks


@dataclass
class TracingSession:
    model_name: str
    model_type: str
    raw_signals: Dict[str, Any]
    features: Dict[str, float]


@dataclass
class Tracer:
    sessions: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def start_llm_session(self, model_name: str, model: Any) -> LLMHooks:
        hooks = LLMHooks(model)
        hooks.attach()
        self.sessions[model_name] = {"hooks": hooks, "type": "llm", "model": model}
        return hooks

    def end_llm_session(self, model_name: str) -> Dict[str, Any]:
        session = self.sessions.pop(model_name, None)
        if not session:
            return {}
        hooks: LLMHooks = session["hooks"]
        hooks.detach()
        return dict(hooks.signals)

    def start_stt_session(self, model_name: str, model: Any) -> tuple[STTHooks, Any]:
        hooks = STTHooks()
        wrapped = hooks.wrap_transcribe(model)
        self.sessions[model_name] = {"hooks": hooks, "type": "stt", "model": model}
        return hooks, wrapped

    def end_stt_session(self, model_name: str) -> Dict[str, Any]:
        session = self.sessions.pop(model_name, None)
        if not session:
            return {}
        hooks: STTHooks = session["hooks"]
        model = session.get("model")
        if model is not None:
            hooks.restore(model)
        return dict(hooks.signals)
