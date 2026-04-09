from __future__ import annotations

import logging
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

    def __init__(self, primary: str, fallback_chain: list[str], backends: dict[str, object]) -> None:
        self.primary = primary
        self.fallback_chain = fallback_chain
        self.backends = backends
        self.last_response: Optional[LLMResponse] = None
        self.last_explain: dict[str, Any] = {}

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
        explain = self._build_effective_route(metadata)
        chain = list(explain["effective"])
        for index, backend_name in enumerate(chain):
            backend = self.backends[backend_name]
            response = backend.generate(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                metadata=metadata,
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
            if response.ok:
                if index > 0:
                    response.was_fallback_used = True
                    response.fallback_from = chain[0]
                    response.fallback_to = backend_name
                response.raw = response.raw or {}
                response.raw["route"] = {
                    "primary": self.primary,
                    "fallback_chain": list(self.fallback_chain),
                    "effective": list(chain),
                    "attempts": attempts,
                    "explain": explain,
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
                }
            },
        )
        self.last_response = final
        self.last_explain = explain
        logger.warning("llm router failed route=%s error=%s", "->".join(chain), final.error)
        return final

    def _build_effective_route(self, metadata: dict[str, Any]) -> dict[str, Any]:
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
        intent = str(metadata.get("intent") or "general").strip().lower()
        backend_health = metadata.get("backend_health") or {}
        health_thresholds = metadata.get("health_thresholds") or {}
        error_threshold = float(health_thresholds.get("error_rate", self._UNHEALTHY_ERROR_RATE))
        latency_threshold = float(health_thresholds.get("latency_ms", self._UNHEALTHY_LATENCY_MS))

        scored: list[dict[str, Any]] = []
        for position, backend in enumerate(base_chain):
            stats = backend_health.get(backend, {})
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
            scored.append(
                {
                    "backend": backend,
                    "position": position,
                    "intent_fit": round(intent_fit, 4),
                    "penalty": round(penalty, 4),
                    "score": round(score, 4),
                    "unhealthy": unhealthy,
                    "stats": {
                        "latency_ms": stats.get("latency_ms"),
                        "error_rate": stats.get("error_rate"),
                        "load": stats.get("load"),
                        "cost": stats.get("cost"),
                    },
                }
            )

        scored.sort(key=lambda row: (row["unhealthy"], -row["score"], row["position"]))
        effective = [row["backend"] for row in scored]
        if self.primary in effective:
            primary_index = effective.index(self.primary)
            effective.insert(0, effective.pop(primary_index))

        return {
            "intent": intent,
            "policy": policy if policy in self._POLICY_WEIGHTS else "balanced",
            "base_route": base_chain,
            "effective": effective,
            "scores": scored,
            "health_thresholds": {"error_rate": error_threshold, "latency_ms": latency_threshold},
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
