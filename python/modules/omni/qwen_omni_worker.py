from __future__ import annotations

import base64
import copy
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from graph.memory_store import MemoryGraphStore  # type: ignore[import-not-found]
from graph.models import ResonanceKnowledgeUnit  # type: ignore[import-not-found]

from .admission import AdmissionDecision, ResonanceAdmissionGate, ResonanceAdmissionPolicy

logger = logging.getLogger(__name__)


@dataclass
class QwenOmniInsight:
    source_question: str
    intent: str | None
    why: str | None
    resonance_score: float
    alignment_score: float
    goal_vector: list[float]
    causal_path: list[dict[str, Any]]
    metadata: dict[str, Any]


class QwenOmniWorker:
    """Minimal MVP worker for Qwen3.5-Omni screen+audio insight generation."""

    def __init__(
        self,
        *,
        graph_store: MemoryGraphStore,
        audio_provider: Callable[[], str | None] | None = None,
        on_response: Callable[[dict[str, Any]], None] | None = None,
        model: str | None = None,
        voice: str | None = None,
        instructions: str | None = None,
        fps: float = 1.0,
        cycle_interval_s: float = 20.0,
        min_store_resonance_score: float = 0.3,
        admission_gate: ResonanceAdmissionGate | None = None,
    ) -> None:
        self.graph_store = graph_store
        self.audio_provider = audio_provider
        self.on_response = on_response
        self.model = model or os.getenv("QWEN_OMNI_MODEL", "qwen3.5-omni-plus-realtime")
        self.voice = voice or os.getenv("QWEN_OMNI_VOICE", "Cherry")
        self.instructions = instructions or os.getenv(
            "QWEN_OMNI_INSTRUCTIONS",
            "Analyze screen and audio context, return concise actionable insight.",
        )
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.max_fps = min(5.0, max(1.0, float(fps)))
        self.min_store_resonance_score = max(0.0, float(min_store_resonance_score))
        self.cycle_interval_s = max(5.0, float(cycle_interval_s))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_frame_ts = 0.0
        self._capture_lock = threading.Lock()
        self._last_insight: dict[str, Any] | None = None
        # If no gate is provided, build a default one from min_store_resonance_score
        # so the existing threshold behaviour is preserved.
        if admission_gate is not None:
            self._admission_gate = admission_gate
        else:
            # Default gate replicates the pre-gate behaviour: a single flat
            # threshold applied to all providers.  Callers who want the
            # stricter fallback penalty should pass an explicit gate.
            self._admission_gate = ResonanceAdmissionGate(
                ResonanceAdmissionPolicy(
                    min_resonance_score=self.min_store_resonance_score,
                    fallback_min_resonance_score=self.min_store_resonance_score,
                )
            )

    @property
    def realtime_enabled(self) -> bool:
        return bool(self.api_key)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="qwen-omni-worker")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.capture_and_analyze(trigger="background")
            except Exception as exc:
                logger.debug("QwenOmniWorker loop failure: %s", exc)
            self._stop_event.wait(timeout=self.cycle_interval_s)

    def capture_and_analyze(self, *, trigger: str = "manual") -> Optional[ResonanceKnowledgeUnit]:
        with self._capture_lock:
            now = time.time()
            if now - self._last_frame_ts < 1.0 / self.max_fps:
                return None

            self._last_frame_ts = now
            frame_payload, frame_meta = self._capture_screen_frame()
            audio_text = self._capture_audio_text()
            model_response = self._analyze_with_model(
                frame_payload=frame_payload,
                frame_meta=frame_meta,
                audio_text=audio_text,
            )
            if model_response is None:
                return None

            if self.on_response is not None:
                try:
                    self.on_response(model_response)
                except Exception as exc:
                    logger.debug("QwenOmniWorker on_response failed: %s", exc)

            insight = self._build_insight(
                model_response=model_response,
                frame_meta=frame_meta,
                audio_text=audio_text,
                trigger=trigger,
            )
            self._last_insight = {
                "source_question": insight.source_question,
                "intent": insight.intent,
                "why": insight.why,
                "resonance_score": insight.resonance_score,
                "alignment_score": insight.alignment_score,
                "goal_vector": list(insight.goal_vector),
                "causal_path": list(insight.causal_path),
                "metadata": dict(insight.metadata),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
            unit = self._build_unit_from_insight(insight)
            decision: AdmissionDecision = self._admission_gate.admit(unit)
            if not decision.allowed:
                logger.debug(
                    "QwenOmniWorker admission denied: %s (trigger=%s)",
                    decision.reason,
                    trigger,
                )
                return None
            try:
                self.graph_store.store_resonance_unit(unit)
            except Exception as exc:
                logger.debug("QwenOmniWorker store_resonance_unit failed: %s", exc)
                return None
            relation_stats = self._derive_relational_edges_from_omni_context(
                unit=unit,
                frame_meta=frame_meta,
                audio_text=audio_text,
            )
            if isinstance(self._last_insight, dict):
                self._last_insight["relational_edges"] = relation_stats
            return unit

    def get_last_insight(self) -> dict[str, Any] | None:
        if self._last_insight is None:
            return None
        return copy.deepcopy(self._last_insight)

    def _capture_screen_frame(self) -> tuple[str | None, dict[str, Any]]:
        try:
            import mss  # type: ignore[import-not-found]
            import mss.tools  # type: ignore[import-not-found]
        except Exception:
            return None, {"capture": "unavailable", "reason": "mss-not-installed"}

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                shot = sct.grab(monitor)
                png_bytes = mss.tools.to_png(shot.rgb, shot.size)
                encoded = base64.b64encode(png_bytes).decode("ascii")
                return encoded, {
                    "capture": "ok",
                    "width": int(shot.width),
                    "height": int(shot.height),
                    "monitor": 1,
                    "image_encoding": "png",
                }
        except Exception as exc:
            return None, {"capture": "error", "reason": str(exc)}

    def _capture_audio_text(self) -> str | None:
        if self.audio_provider is None:
            return None
        try:
            text = self.audio_provider()
            if not text:
                return None
            return str(text).strip()[:500]
        except Exception as exc:
            logger.debug("QwenOmniWorker audio capture failed: %s", exc)
            return None

    def _analyze_with_model(
        self,
        *,
        frame_payload: str | None,
        frame_meta: dict[str, Any],
        audio_text: str | None,
    ) -> dict[str, Any] | None:
        if self.realtime_enabled:
            result = self._analyze_with_dashscope_realtime(
                frame_payload=frame_payload,
                frame_meta=frame_meta,
                audio_text=audio_text,
            )
            if result is not None:
                return result

        return self._analyze_with_fallback(frame_meta=frame_meta, audio_text=audio_text)

    def _analyze_with_dashscope_realtime(
        self,
        *,
        frame_payload: str | None,
        frame_meta: dict[str, Any],
        audio_text: str | None,
    ) -> dict[str, Any] | None:
        try:
            import dashscope  # type: ignore[import-not-found]

            conversation_cls = getattr(dashscope, "OmniRealtimeConversation", None)
            if conversation_cls is None:
                return None

            conversation = conversation_cls(
                model=self.model,
                api_key=self.api_key,
                voice=self.voice,
                instructions=self.instructions,
            )
            payload: dict[str, Any] = {
                "modalities": ["text", "audio", "vision"],
                "input": {
                    "screen_frame_b64": frame_payload,
                    "screen_meta": frame_meta,
                    "audio_text": audio_text,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
            # TODO: wire stream chunks + WS reconnection policy when SDK surface is stable.
            if hasattr(conversation, "create"):
                response = conversation.create(payload)
            elif hasattr(conversation, "call"):
                response = conversation.call(payload)
            else:
                return None
            return self._normalize_model_response(response)
        except Exception as exc:
            logger.debug("DashScope realtime analyze failed: %s", exc)
            return None

    def _analyze_with_fallback(
        self,
        *,
        frame_meta: dict[str, Any],
        audio_text: str | None,
    ) -> dict[str, Any]:
        has_screen = frame_meta.get("capture") == "ok"
        observation = "screen-visible" if has_screen else "screen-unavailable"
        if audio_text:
            observation = f"{observation};audio:{audio_text[:120]}"
        return {
            "text": f"MVP fallback insight: {observation}",
            "intent": "situational_awareness",
            "why": "maintain_background_context",
            "resonance_score": 0.34 if has_screen else 0.12,
            "alignment_score": 0.30,
            "causal_path": [
                {
                    "step": "multimodal_capture",
                    "strategy": "screen_audio_fallback",
                    "outcome": observation,
                    "resonance_delta": 0.05 if has_screen else -0.05,
                }
            ],
            "metadata": {
                "provider": "fallback",
                "frame_meta": frame_meta,
                "audio_text": audio_text,
                "model": self.model,
            },
        }

    def _normalize_model_response(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return response
        text = ""
        if hasattr(response, "output_text"):
            text = str(getattr(response, "output_text"))
        elif hasattr(response, "text"):
            text = str(getattr(response, "text"))
        return {
            "text": text,
            "intent": "situational_awareness",
            "why": "background_monitoring",
            "resonance_score": 0.4 if text else 0.2,
            "alignment_score": 0.35,
            "causal_path": [
                {
                    "step": "realtime_inference",
                    "strategy": "dashscope_ws",
                    "outcome": "insight_generated" if text else "empty_text",
                    "resonance_delta": 0.07 if text else -0.02,
                }
            ],
            "metadata": {"provider": "dashscope", "model": self.model},
        }

    def _build_insight(
        self,
        *,
        model_response: dict[str, Any],
        frame_meta: dict[str, Any],
        audio_text: str | None,
        trigger: str,
    ) -> QwenOmniInsight:
        source_question = str(model_response.get("text") or "screen/audio context")
        causal_path_raw = model_response.get("causal_path")
        causal_path = list(causal_path_raw) if isinstance(causal_path_raw, list) else []
        return QwenOmniInsight(
            source_question=source_question,
            intent=model_response.get("intent"),
            why=model_response.get("why"),
            resonance_score=float(model_response.get("resonance_score", 0.0) or 0.0),
            alignment_score=float(model_response.get("alignment_score", 0.0) or 0.0),
            goal_vector=[],
            causal_path=causal_path,
            metadata={
                "source": "qwen_omni_worker",
                "trigger": trigger,
                "frame_meta": frame_meta,
                "audio_text": audio_text,
                "model": self.model,
                "voice": self.voice,
                "instructions": self.instructions,
                "provider": "dashscope_realtime" if self.realtime_enabled else "fallback",
                **dict(model_response.get("metadata") or {}),
            },
        )

    def _build_unit_from_insight(self, insight: QwenOmniInsight) -> ResonanceKnowledgeUnit:
        return ResonanceKnowledgeUnit(
            source_question=insight.source_question,
            intent=insight.intent,
            why=insight.why,
            goal_vector=insight.goal_vector,
            causal_path=insight.causal_path,
            resonance_score=insight.resonance_score,
            alignment_score=insight.alignment_score,
            metadata=insight.metadata,
        )

    def _derive_relational_edges_from_omni_context(
        self,
        *,
        unit: ResonanceKnowledgeUnit,
        frame_meta: dict[str, Any],
        audio_text: str | None,
    ) -> dict[str, Any]:
        """Create or suggest relation edges from omni context (screen/audio)."""
        try:
            from agent.relational_policy_engine import suggest_edge_from_resonance
        except Exception:
            try:
                from modules.agent.relational_policy_engine import suggest_edge_from_resonance
            except Exception:
                return {"auto_created": 0, "suggested_review": 0, "candidates": []}

        source_tags: list[str] = []
        if str((frame_meta or {}).get("capture") or "") == "ok":
            source_tags.append("omni_screen")
        if audio_text:
            source_tags.append("omni_audio")
        if not source_tags:
            source_tags.append("omni_unknown")

        candidates = self.graph_store.find_relevant_units(
            intent=unit.intent,
            why=unit.why,
            query_text=unit.source_question,
            top_k=3,
        )
        auto_created = 0
        suggested_review = 0
        review_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            if candidate.unit_id == unit.unit_id:
                continue
            edge = suggest_edge_from_resonance(unit, candidate)
            if edge is None:
                continue
            confidence = float(
                (
                    float(edge.strength or 0.0)
                    + min(float(unit.alignment_score or 0.0), float(candidate.alignment_score or 0.0))
                )
                / 2.0
            )
            edge.metadata = {
                **dict(edge.metadata or {}),
                "source_tags": source_tags,
                "confidence": round(confidence, 4),
                "mode": "auto_commit" if confidence >= 0.55 else "review_candidate",
            }
            if confidence >= 0.55:
                self.graph_store.store_relational_edge(unit.unit_id, edge)
                auto_created += 1
            else:
                suggested_review += 1
                review_candidates.append(
                    {
                        "target_unit_id": candidate.unit_id,
                        "relation_type": edge.relation_type,
                        "strength": round(confidence, 4),
                        "source_tags": source_tags,
                    }
                )

        if review_candidates:
            unit.metadata = dict(unit.metadata or {})
            unit.metadata["relation_candidates"] = review_candidates
            self.graph_store.store_resonance_unit(unit)
        return {
            "auto_created": auto_created,
            "suggested_review": suggested_review,
            "candidates": review_candidates,
            "source_tags": source_tags,
        }
