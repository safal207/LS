from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Optional

from modules.llm.quality import LLMQualityAssessment, evaluate_llm_answer_quality
from modules.llm.rust_meritocracy import rust_meritocracy_available, rust_meritocracy_select

from .base import LLMResponse, normalize_messages

logger = logging.getLogger(__name__)


def _parse_route(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [segment.strip().lower() for segment in str(value).split(",")]
    return [segment for segment in parts if segment]


class MeritocracyLLMAdapter:
    def __init__(
        self,
        *,
        backends: dict[str, object],
        candidate_order: list[str],
        enabled: bool = True,
        min_overall: float = 0.35,
        min_relevance: float = 0.25,
        min_thread_relevance: float = 0.25,
        max_hallucination_risk: float = 0.65,
    ) -> None:
        self.provider = "meritocracy"
        self.model = "ensemble"
        self.backends = backends
        self.candidate_order = [name for name in candidate_order if name in backends]
        self.enabled = enabled
        self.min_overall = float(min_overall)
        self.min_relevance = float(min_relevance)
        self.min_thread_relevance = float(min_thread_relevance)
        self.max_hallucination_risk = float(max_hallucination_risk)
        self.last_selection: Optional[dict[str, Any]] = None
        self.rust_available = rust_meritocracy_available()

    def _extract_question(self, messages, system_prompt: Optional[str] = None) -> str:
        prompt_messages = normalize_messages(messages, system_prompt=system_prompt)
        for message in reversed(prompt_messages):
            if message.get("role") == "user" and message.get("content"):
                return str(message["content"]).strip()
        if prompt_messages:
            return str(prompt_messages[-1].get("content", "")).strip()
        return ""

    def _score_response(
        self,
        *,
        question: str,
        answer: str,
        thread_context: str,
    ) -> LLMQualityAssessment:
        return evaluate_llm_answer_quality(
            question=question,
            answer=answer,
            thread_context=thread_context,
        )

    def _selection_policy(self) -> dict[str, float]:
        return {
            "min_overall": self.min_overall,
            "min_relevance": self.min_relevance,
            "min_thread_relevance": self.min_thread_relevance,
            "max_hallucination_risk": self.max_hallucination_risk,
        }

    def _rank_candidates_python(self, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        ranked = sorted(
            candidates,
            key=lambda item: (
                1 if item["ok"] else 0,
                item["quality"]["overall"],
                item["quality"]["relevance"],
                item["quality"]["thread_relevance"],
                -item["quality"]["hallucination_risk"],
                -item["latency_ms"],
            ),
            reverse=True,
        )

        passing = [
            item
            for item in ranked
            if item["quality"]["overall"] >= self.min_overall
            and item["quality"]["relevance"] >= self.min_relevance
            and item["quality"]["thread_relevance"] >= self.min_thread_relevance
            and item["quality"]["hallucination_risk"] <= self.max_hallucination_risk
        ]
        return ranked, (passing[0] if passing else ranked[0])

    def generate(
        self,
        messages,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
        *,
        stream: bool = False,
        on_token=None,
    ) -> LLMResponse:
        _ = stream
        _ = on_token
        start = perf_counter()
        metadata = metadata or {}
        if not self.enabled:
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=0.0,
                error="meritocracy backend disabled",
            )

        question = self._extract_question(messages, system_prompt=system_prompt)
        thread_context = str(metadata.get("thread_context") or question or "").strip()
        if not question.strip():
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=0.0,
                error="meritocracy backend missing question",
            )

        candidates: list[dict[str, Any]] = []
        for backend_name in self.candidate_order:
            backend = self.backends.get(backend_name)
            if backend is None:
                continue
            response = backend.generate(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                metadata={**metadata, "meritocracy_candidate": backend_name},
            )
            quality = self._score_response(
                question=question,
                answer=response.text or "",
                thread_context=thread_context,
            )
            candidate = {
                "backend": backend_name,
                "provider": response.provider,
                "model": response.model,
                "ok": response.ok,
                "latency_ms": round(float(response.latency_ms), 2),
                "error": response.error,
                "quality": quality.to_dict(),
                "response": response,
            }
            candidates.append(candidate)

        if not candidates:
            latency_ms = (perf_counter() - start) * 1000
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=latency_ms,
                error="meritocracy backend has no candidates",
            )

        selected_backend = None
        selected_provider = None
        selected_model = None
        selected_quality = None
        rust_result = None
        if self.rust_available:
            rust_result = rust_meritocracy_select(
                question=question,
                thread_context=thread_context,
                candidates=[
                    {
                        "backend": item["backend"],
                        "provider": item["provider"],
                        "model": item["model"],
                        "text": item["response"].text,
                        "ok": item["ok"],
                        "latency_ms": item["latency_ms"],
                        "error": item["error"],
                    }
                    for item in candidates
                ],
                policy=self._selection_policy(),
            )

        if rust_result:
            ranking_by_backend = {item["backend"]: item for item in candidates}
            ranked = []
            for ranked_item in rust_result.get("ranking", []):
                backend_name = ranked_item.get("backend")
                original = ranking_by_backend.get(backend_name)
                if not original:
                    continue
                merged = dict(original)
                merged["quality"] = ranked_item.get("quality", original["quality"])
                ranked.append(merged)
            if not ranked:
                ranked, chosen = self._rank_candidates_python(candidates)
                selected_backend = chosen["backend"]
                selected_provider = chosen["provider"]
                selected_model = chosen["model"]
                selected_quality = chosen["quality"]
            else:
                selected_backend = rust_result.get("selected_backend")
                chosen = next((item for item in ranked if item["backend"] == selected_backend), ranked[0])
                selected_provider = rust_result.get("selected_provider", chosen["provider"])
                selected_model = rust_result.get("selected_model", chosen["model"])
                selected_quality = rust_result.get("selected_quality", chosen["quality"])
        else:
            ranked, chosen = self._rank_candidates_python(candidates)
            selected_backend = chosen["backend"]
            selected_provider = chosen["provider"]
            selected_model = chosen["model"]
            selected_quality = chosen["quality"]

        winner: LLMResponse = chosen["response"]

        latency_ms = (perf_counter() - start) * 1000
        raw = dict(winner.raw or {})
        raw["meritocracy"] = {
            "question": question,
            "thread_context": thread_context,
            "candidate_order": list(self.candidate_order),
            "selection_engine": "rust" if rust_result else "python",
            "ranking": [
                {
                    "backend": item["backend"],
                    "provider": item["provider"],
                    "model": item["model"],
                    "ok": item["ok"],
                    "latency_ms": item["latency_ms"],
                    "error": item["error"],
                    "quality": item["quality"],
                }
                for item in ranked
            ],
            "selected_backend": selected_backend,
            "selected_provider": selected_provider,
            "selected_model": selected_model,
            "selected_quality": selected_quality,
            "selection_policy": {
                "min_overall": self.min_overall,
                "min_relevance": self.min_relevance,
                "min_thread_relevance": self.min_thread_relevance,
                "max_hallucination_risk": self.max_hallucination_risk,
            },
        }

        selected = LLMResponse(
            text=winner.text,
            model=winner.model,
            provider=winner.provider,
            latency_ms=latency_ms,
            raw=raw,
            error=winner.error,
            was_fallback_used=winner.was_fallback_used,
            fallback_from=winner.fallback_from,
            fallback_to=winner.fallback_to,
        )
        self.last_selection = raw["meritocracy"]
        logger.info(
            "meritocracy selected backend=%s provider=%s model=%s overall=%.3f",
            chosen["backend"],
            chosen["provider"],
            chosen["model"],
            chosen["quality"]["overall"],
        )
        return selected
