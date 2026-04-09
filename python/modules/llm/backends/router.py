from __future__ import annotations

import logging
from hashlib import sha256
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from config import (
    GONKA_API_KEY,
    GONKA_BASE_URL,
    GONKA_ENABLED,
    GONKA_MODEL,
    GONKA_TIMEOUT_SEC,
    MIMO_API_KEY,
    MIMO_BASE_URL,
    MIMO_ENABLED,
    MIMO_MODEL,
    MIMO_TIMEOUT_SEC,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    GROQ_TIMEOUT_SEC,
    LLM_BACKEND,
    LLM_FALLBACK_BACKEND,
    LLM_MERITOCRACY_BACKENDS,
    LLM_MERITOCRACY_ENABLED,
    LLM_MERITOCRACY_MAX_HALLUCINATION_RISK,
    LLM_MERITOCRACY_MIN_OVERALL,
    LLM_MERITOCRACY_MIN_RELEVANCE,
    LLM_MERITOCRACY_MIN_THREAD_RELEVANCE,
    USE_CLOUD_LLM,
    USE_GROQ,
)

from .base import LLMResponse
from .cloud_adapter import CloudLLMAdapter
from .gonka_adapter import GonkaLLMAdapter
from .meritocracy import MeritocracyLLMAdapter
from .mimo_adapter import MimoLLMAdapter
from .local_adapter import LocalLLMAdapter

logger = logging.getLogger(__name__)


def _parse_route(value: Optional[str]) -> list[str]:
    if not value:
        return []
    parts = [segment.strip().lower() for segment in str(value).split(",")]
    return [segment for segment in parts if segment]


@dataclass
class BackendCircuitState:
    consecutive_failures: int = 0
    opened_until: Optional[datetime] = None
    total_success: int = 0
    total_failures: int = 0

    @property
    def is_open(self) -> bool:
        if not self.opened_until:
            return False
        return datetime.now(timezone.utc) < self.opened_until


class LLMBackendRouter:
    _INTENT_CAPABILITY: dict[str, dict[str, float]] = {
        "realtime": {"local": 1.0, "cloud": 0.75, "gonka": 0.65, "mimo": 0.55, "meritocracy": 0.7},
        "batch": {"cloud": 1.0, "gonka": 0.85, "mimo": 0.8, "local": 0.55, "meritocracy": 0.9},
        "streaming": {"cloud": 1.0, "gonka": 0.8, "local": 0.7, "mimo": 0.6, "meritocracy": 0.85},
    }
    _POLICY_WEIGHTS: dict[str, dict[str, float]] = {
        "balanced": {"latency": 0.35, "error": 0.35, "load": 0.15, "cost": 0.15},
        "latency_optimized": {"latency": 0.6, "error": 0.2, "load": 0.1, "cost": 0.1},
        "cost_optimized": {"latency": 0.15, "error": 0.2, "load": 0.15, "cost": 0.5},
    }
    _UNHEALTHY_ERROR_RATE = 0.10
    _UNHEALTHY_LATENCY_MS = 8000.0
    _BREAKER_FAILURE_THRESHOLD = 3
    _BREAKER_COOLDOWN_SECONDS = 30

    def __init__(self, primary: str, fallback_chain: list[str], backends: dict[str, object]) -> None:
        self.primary = primary
        self.fallback_chain = fallback_chain
        self.backends = backends
        self.last_response: Optional[LLMResponse] = None
        self.last_explain: dict[str, Any] = {}
        self._circuit: dict[str, BackendCircuitState] = {}
        self._runtime_policy_override: Optional[str] = None
        self._runtime_threshold_overrides: dict[str, Any] = {}
        self._stats: dict[str, Any] = {
            "requests_total": 0,
            "fallback_total": 0,
            "ab_variant_selected_total": 0,
            "shadow_evaluations_total": 0,
            "backend_success_total": {},
            "backend_failure_total": {},
        }

    @property
    def route(self) -> list[str]:
        ordered = [self.primary] + list(self.fallback_chain)
        seen: set[str] = set()
        result: list[str] = []
        for name in ordered:
            if name and name not in seen and name in self.backends:
                result.append(name)
                seen.add(name)
        return result

    def generate(
        self,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        timeout=None,
        metadata=None,
        *,
        stream: bool = False,
        on_token=None,
    ) -> LLMResponse:
        errors: list[str] = []
        attempts: list[dict[str, object]] = []
        metadata = metadata or {}
        effective_metadata = self._resolve_routing_metadata(metadata, messages=messages)
        explain = self._build_effective_route(effective_metadata, messages=messages)
        self._attach_shadow_explain(explain, metadata=metadata, messages=messages)
        chain = list(explain["effective"])
        self._stats["requests_total"] += 1
        for index, backend_name in enumerate(chain):
            backend = self.backends[backend_name]
            response = backend.generate(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                metadata=effective_metadata,
                stream=stream,
                on_token=on_token,
            )
            attempts.append(
                {
                    "backend": backend_name,
                    "provider": response.provider,
                    "model": response.model,
                    "ok": response.ok,
                    "error": response.error,
                    "latency_ms": response.latency_ms,
                    "was_fallback_used": response.was_fallback_used,
                    "fallback_from": response.fallback_from,
                    "fallback_to": response.fallback_to,
                }
            )
            self._record_circuit_outcome(backend_name, response.ok, metadata=effective_metadata)
            if response.ok:
                success_totals = self._stats["backend_success_total"]
                success_totals[backend_name] = int(success_totals.get(backend_name, 0)) + 1
            else:
                failure_totals = self._stats["backend_failure_total"]
                failure_totals[backend_name] = int(failure_totals.get(backend_name, 0)) + 1
            if response.ok:
                if index > 0:
                    response.was_fallback_used = True
                    response.fallback_from = chain[0]
                    response.fallback_to = backend_name
                    self._stats["fallback_total"] += 1
                response.raw = response.raw or {}
                response.raw["route"] = {
                    "primary": self.primary,
                    "fallback_chain": list(self.fallback_chain),
                    "effective": list(chain),
                    "attempts": attempts,
                    "explain": explain,
                    "stats": self._stats_snapshot(),
                }
                self.last_response = response
                self.last_explain = explain
                return response
            errors.append(f"{backend_name}: {response.error or 'unknown error'}")

        final = LLMResponse(
            text="",
            model="",
            provider=chain[0] if chain else "unknown",
            latency_ms=0.0,
            error="; ".join(errors) if errors else "no backend available",
            was_fallback_used=len(chain) > 1,
            fallback_from=chain[0] if len(chain) > 1 else None,
            fallback_to=chain[-1] if len(chain) > 1 else None,
            raw={
                "route": {
                    "primary": self.primary,
                    "fallback_chain": list(self.fallback_chain),
                    "effective": list(chain),
                    "attempts": attempts,
                    "explain": explain,
                    "stats": self._stats_snapshot(),
                }
            },
        )
        self.last_response = final
        self.last_explain = explain
        logger.warning("llm router failed route=%s error=%s", "->".join(chain), final.error)
        return final

    def set_runtime_overrides(
        self,
        *,
        policy: Optional[str] = None,
        health_thresholds: Optional[dict[str, Any]] = None,
    ) -> None:
        self._runtime_policy_override = str(policy).strip().lower() if policy else None
        self._runtime_threshold_overrides = dict(health_thresholds or {})

    def clear_runtime_overrides(self) -> None:
        self._runtime_policy_override = None
        self._runtime_threshold_overrides = {}

    def _build_effective_route(self, metadata: dict[str, Any], *, messages: Any = None) -> dict[str, Any]:
        base_chain = self.route
        if not base_chain:
            return {
                "intent": "general",
                "policy": "balanced",
                "base_route": [],
                "effective": [],
                "scores": [],
            }

        policy = str(metadata.get("routing_policy") or metadata.get("policy") or "balanced").strip().lower()
        weights = self._POLICY_WEIGHTS.get(policy, self._POLICY_WEIGHTS["balanced"])
        intent = self._resolve_intent(messages=messages, metadata=metadata)
        backend_health = metadata.get("backend_health") or {}
        health_thresholds = metadata.get("health_thresholds") or {}
        error_threshold = float(health_thresholds.get("error_rate", self._UNHEALTHY_ERROR_RATE))
        latency_threshold = float(health_thresholds.get("latency_ms", self._UNHEALTHY_LATENCY_MS))
        breaker_threshold = int(metadata.get("breaker_failure_threshold") or self._BREAKER_FAILURE_THRESHOLD)
        breaker_cooldown_seconds = int(metadata.get("breaker_cooldown_seconds") or self._BREAKER_COOLDOWN_SECONDS)

        scored: list[dict[str, Any]] = []
        for position, backend in enumerate(base_chain):
            stats = backend_health.get(backend, {})
            state = self._circuit.setdefault(backend, BackendCircuitState())
            latency_norm = self._normalize_value(stats.get("latency_ms"), cap=5000.0)
            error_norm = self._normalize_value(stats.get("error_rate"), cap=1.0)
            load_norm = self._normalize_value(stats.get("load"), cap=1.0)
            cost_norm = self._normalize_value(stats.get("cost"), cap=1.0)
            intent_fit = self._intent_fit(intent, backend)
            penalty = (
                weights["latency"] * latency_norm
                + weights["error"] * error_norm
                + weights["load"] * load_norm
                + weights["cost"] * cost_norm
            )
            score = intent_fit - penalty
            unhealthy = bool(
                (stats.get("error_rate") is not None and float(stats["error_rate"]) >= error_threshold)
                or (stats.get("latency_ms") is not None and float(stats["latency_ms"]) >= latency_threshold)
            )
            breaker_open = state.is_open
            scored.append(
                {
                    "backend": backend,
                    "position": position,
                    "intent_fit": round(intent_fit, 4),
                    "penalty": round(penalty, 4),
                    "score": round(score, 4),
                    "unhealthy": unhealthy,
                    "breaker_open": breaker_open,
                    "stats": {
                        "latency_ms": stats.get("latency_ms"),
                        "error_rate": stats.get("error_rate"),
                        "load": stats.get("load"),
                        "cost": stats.get("cost"),
                    },
                    "circuit": {
                        "consecutive_failures": state.consecutive_failures,
                        "opened_until": state.opened_until.isoformat() if state.opened_until else None,
                        "total_success": state.total_success,
                        "total_failures": state.total_failures,
                    },
                }
            )

        scored.sort(key=lambda row: (row["breaker_open"], row["unhealthy"], -row["score"], row["position"]))
        effective = [row["backend"] for row in scored]
        pin_primary = bool(metadata.get("pin_primary", False))
        if pin_primary and self.primary in effective:
            primary_index = effective.index(self.primary)
            effective.insert(0, effective.pop(primary_index))

        return {
            "intent": intent,
            "policy": policy if policy in self._POLICY_WEIGHTS else "balanced",
            "routing_mode": str(metadata.get("routing_mode") or "primary").strip().lower(),
            "ab_variant_selected": bool(metadata.get("ab_variant_selected", False)),
            "ab_variant_ratio": metadata.get("ab_variant_ratio"),
            "base_route": base_chain,
            "effective": effective,
            "scores": scored,
            "health_thresholds": {"error_rate": error_threshold, "latency_ms": latency_threshold},
            "breaker": {"failure_threshold": breaker_threshold, "cooldown_seconds": breaker_cooldown_seconds},
            "pin_primary": pin_primary,
            "runtime_overrides": {
                "policy": self._runtime_policy_override,
                "health_thresholds": self._runtime_threshold_overrides,
            },
        }

    @classmethod
    def _normalize_value(cls, value: Any, *, cap: float) -> float:
        if value is None:
            return 0.0
        try:
            raw = float(value)
        except (TypeError, ValueError):
            return 0.0
        if raw < 0:
            return 0.0
        if cap <= 0:
            return 0.0
        return min(raw / cap, 1.0)

    @classmethod
    def _intent_fit(cls, intent: str, backend: str) -> float:
        profile = cls._INTENT_CAPABILITY.get(intent)
        if not profile:
            return 0.7
        return profile.get(backend, 0.5)

    @classmethod
    def _resolve_intent(cls, *, messages: Any, metadata: dict[str, Any]) -> str:
        explicit = str(metadata.get("intent") or "").strip().lower()
        if explicit:
            return explicit

        text = ""
        if isinstance(messages, str):
            text = messages.lower()
        elif isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict) and str(msg.get("role", "")).lower() == "user":
                    text = str(msg.get("content", "")).lower()
                    break
        if any(token in text for token in ("stream", "sse", "websocket", "realtime audio")):
            return "streaming"
        if any(token in text for token in ("fast", "urgent", "asap", "quick", "now")):
            return "realtime"
        if any(token in text for token in ("batch", "offline", "bulk", "async")):
            return "batch"
        return "general"

    def _record_circuit_outcome(self, backend: str, ok: bool, *, metadata: dict[str, Any]) -> None:
        state = self._circuit.setdefault(backend, BackendCircuitState())
        threshold = int(metadata.get("breaker_failure_threshold") or self._BREAKER_FAILURE_THRESHOLD)
        cooldown_seconds = int(metadata.get("breaker_cooldown_seconds") or self._BREAKER_COOLDOWN_SECONDS)
        if ok:
            state.total_success += 1
            state.consecutive_failures = 0
            state.opened_until = None
            return

        state.total_failures += 1
        state.consecutive_failures += 1
        if state.consecutive_failures >= threshold:
            state.opened_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)

    def _resolve_routing_metadata(self, metadata: dict[str, Any], *, messages: Any) -> dict[str, Any]:
        merged = dict(metadata)
        if self._runtime_policy_override and not merged.get("policy") and not merged.get("routing_policy"):
            merged["policy"] = self._runtime_policy_override

        runtime_thresholds = dict(self._runtime_threshold_overrides)
        if runtime_thresholds:
            user_thresholds = dict(merged.get("health_thresholds") or {})
            user_thresholds = {**runtime_thresholds, **user_thresholds}
            merged["health_thresholds"] = user_thresholds

        mode = str(merged.get("routing_mode") or "primary").strip().lower()
        if mode == "ab":
            ratio = float(merged.get("ab_variant_ratio", 0.0))
            if self._is_ab_variant_request(merged, ratio=ratio):
                variant_policy = str(merged.get("ab_variant_policy") or "").strip().lower()
                if variant_policy:
                    merged["policy"] = variant_policy
                merged["ab_variant_selected"] = True
                self._stats["ab_variant_selected_total"] += 1
            else:
                merged["ab_variant_selected"] = False
            merged["ab_variant_ratio"] = ratio
        return merged

    def _attach_shadow_explain(self, explain: dict[str, Any], *, metadata: dict[str, Any], messages: Any) -> None:
        mode = str(metadata.get("routing_mode") or "").strip().lower()
        if mode != "shadow":
            return
        shadow_policy = str(metadata.get("shadow_policy") or "").strip().lower()
        shadow_metadata = dict(metadata)
        if shadow_policy:
            shadow_metadata["policy"] = shadow_policy
        shadow_metadata.pop("routing_mode", None)
        shadow = self._build_effective_route(shadow_metadata, messages=messages)
        explain["shadow"] = {
            "policy": shadow.get("policy"),
            "effective": shadow.get("effective"),
            "scores": shadow.get("scores"),
        }
        self._stats["shadow_evaluations_total"] += 1

    @staticmethod
    def _is_ab_variant_request(metadata: dict[str, Any], *, ratio: float) -> bool:
        if ratio <= 0:
            return False
        if ratio >= 1:
            return True
        request_key = str(metadata.get("request_id") or metadata.get("trace_id") or metadata.get("user_id") or "default")
        digest = sha256(request_key.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        return bucket < ratio

    def _stats_snapshot(self) -> dict[str, Any]:
        return {
            "requests_total": int(self._stats["requests_total"]),
            "fallback_total": int(self._stats["fallback_total"]),
            "ab_variant_selected_total": int(self._stats["ab_variant_selected_total"]),
            "shadow_evaluations_total": int(self._stats["shadow_evaluations_total"]),
            "backend_success_total": dict(self._stats["backend_success_total"]),
            "backend_failure_total": dict(self._stats["backend_failure_total"]),
        }


def build_llm_backend(
    *,
    local_handler=None,
    local_model: str = "",
    local_fallback_model: str = "",
    backend: Optional[str] = None,
    fallback_chain: Optional[str] = None,
) -> LLMBackendRouter:
    primary = (backend or LLM_BACKEND or "").strip().lower()
    fallbacks = _parse_route(fallback_chain or LLM_FALLBACK_BACKEND)

    if not primary:
        if GONKA_ENABLED and GONKA_API_KEY:
            primary = "gonka"
        elif MIMO_ENABLED and MIMO_API_KEY:
            primary = "mimo"
        elif USE_GROQ or USE_CLOUD_LLM:
            primary = "cloud"
        else:
            primary = "local"

    if not fallbacks:
        if primary == "gonka":
            fallbacks = ["mimo", "cloud", "local"]
        elif primary == "mimo":
            fallbacks = ["cloud", "local"]
        elif primary == "meritocracy":
            fallbacks = ["mimo", "cloud", "local"]
        elif primary == "cloud":
            fallbacks = ["local"]
        else:
            fallbacks = []

    backends: dict[str, object] = {
        "local": LocalLLMAdapter(
            handler=local_handler,
            model=local_model,
            fallback_model=local_fallback_model,
        ),
        "cloud": CloudLLMAdapter(
            model=GROQ_MODEL,
            base_url=GROQ_BASE_URL,
            api_key=GROQ_API_KEY,
            timeout_sec=GROQ_TIMEOUT_SEC,
            enabled=bool(USE_GROQ or USE_CLOUD_LLM or GROQ_API_KEY),
        ),
        "gonka": GonkaLLMAdapter(
            model=GONKA_MODEL,
            base_url=GONKA_BASE_URL,
            api_key=GONKA_API_KEY,
            timeout_sec=GONKA_TIMEOUT_SEC,
            enabled=bool(GONKA_ENABLED and GONKA_API_KEY),
        ),
        "mimo": MimoLLMAdapter(
            model=MIMO_MODEL,
            base_url=MIMO_BASE_URL,
            api_key=MIMO_API_KEY,
            timeout_sec=MIMO_TIMEOUT_SEC,
            enabled=bool(MIMO_ENABLED and MIMO_API_KEY),
        ),
    }
    if primary == "meritocracy" or LLM_MERITOCRACY_ENABLED:
        candidate_order = _parse_route(LLM_MERITOCRACY_BACKENDS) or ["gonka", "mimo", "cloud", "local"]
        backends["meritocracy"] = MeritocracyLLMAdapter(
            backends=backends,
            candidate_order=candidate_order,
            enabled=bool(primary == "meritocracy" or LLM_MERITOCRACY_ENABLED),
            min_overall=LLM_MERITOCRACY_MIN_OVERALL,
            min_relevance=LLM_MERITOCRACY_MIN_RELEVANCE,
            min_thread_relevance=LLM_MERITOCRACY_MIN_THREAD_RELEVANCE,
            max_hallucination_risk=LLM_MERITOCRACY_MAX_HALLUCINATION_RISK,
        )
    return LLMBackendRouter(primary=primary, fallback_chain=fallbacks, backends=backends)
