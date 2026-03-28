from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional

from .memory_store import MemoryGraphStore
from .models import MemoryCase, ResonanceKnowledgeUnit
from .retriever import MemoryGraphRetriever
from .reuse import decide_reuse


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_contributors(
    contributors: list[Any] | None,
) -> list[dict[str, Any] | str]:
    normalized: list[dict[str, Any] | str] = []
    for contributor in contributors or []:
        if hasattr(contributor, "to_dict"):
            normalized.append(contributor.to_dict())
        elif isinstance(contributor, dict):
            normalized.append(contributor)
        else:
            normalized.append(str(contributor))
    return normalized


def _build_resonance_causal_path(item: dict[str, Any]) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []

    intent = item.get("_intent") or item.get("intent")
    why = item.get("_why") or item.get("why")
    why_strategy = item.get("_why_strategy") or {}
    network_plan = item.get("_network_plan") or {}

    if intent:
        path.append(
            {
                "step": "intent_detected",
                "strategy": str(intent),
                "outcome": "intent_attached",
                "resonance_delta": 0.0,
            }
        )

    if why:
        path.append(
            {
                "step": "why_detected",
                "strategy": str(why),
                "outcome": "motivation_attached",
                "resonance_delta": 0.0,
            }
        )

    answer_type = why_strategy.get("answer_type")
    if answer_type:
        path.append(
            {
                "step": "strategy_selected",
                "strategy": str(answer_type),
                "outcome": "response_strategy_attached",
                "resonance_delta": 0.0,
            }
        )

    route_key = network_plan.get("route_key")
    if route_key:
        path.append(
            {
                "step": "route_selected",
                "strategy": str(route_key),
                "outcome": "network_route_attached",
                "resonance_delta": 0.0,
            }
        )

    return path


def _should_store_resonance_unit(
    item: dict[str, Any],
    answer_text: str,
    answer_quality: dict[str, Any] | None,
) -> bool:
    text = (item.get("clean_text") or item.get("text") or "").strip()
    if not text:
        return False

    if not (answer_text or "").strip():
        return False

    graph_runtime = item.get("_graph_runtime") or {}
    graph_mode = (
        item.get("_graph_mode")
        or item.get("graph_mode")
        or graph_runtime.get("mode")
    )
    if graph_mode == "reuse":
        return False

    intent = item.get("_intent") or item.get("intent")
    why = item.get("_why") or item.get("why")
    why_strategy = item.get("_why_strategy") or {}
    network_plan = item.get("_network_plan") or {}

    has_semantic_signal = any([intent, why, bool(why_strategy), bool(network_plan)])
    if not has_semantic_signal:
        return False

    resonance_score = _as_float(item.get("_resonance_score"), 0.0)
    quality_payload = answer_quality or {}
    overall = _as_float(
        quality_payload.get("overall")
        or quality_payload.get("score")
        or quality_payload.get("quality"),
        0.0,
    )

    return resonance_score >= 0.55 or overall >= 0.70


def _build_resonance_unit(
    item: dict[str, Any],
    *,
    answer_text: str,
    thread_context: str | None,
    answer_quality: dict[str, Any] | None,
    contributors: list[dict[str, Any]] | None,
) -> ResonanceKnowledgeUnit:
    network_plan = item.get("_network_plan") or {}
    graph_runtime = item.get("_graph_runtime") or {}
    quality_payload = answer_quality or {}
    graph_mode = (
        item.get("_graph_mode")
        or item.get("graph_mode")
        or graph_runtime.get("mode")
    )
    goal_vector_raw = network_plan.get("goal_vector")

    if isinstance(goal_vector_raw, list):
        goal_vector = goal_vector_raw
        goal_profile = None
    else:
        goal_vector = []
        goal_profile = (
            goal_vector_raw
            if isinstance(goal_vector_raw, (dict, str, int, float, bool))
            or goal_vector_raw is None
            else str(goal_vector_raw)
        )

    resonance_score = _as_float(item.get("_resonance_score"), 0.0)
    alignment_score = _as_float(
        item.get("_goal_alignment_score") or quality_payload.get("goal_alignment"),
        0.0,
    )

    return ResonanceKnowledgeUnit(
        source_question=(item.get("clean_text") or item.get("text") or "").strip(),
        clean_question=(item.get("clean_text") or None),
        intent=item.get("_intent") or item.get("intent"),
        why=item.get("_why") or item.get("why"),
        goal_vector=goal_vector,
        causal_path=_build_resonance_causal_path(item),
        resonance_score=resonance_score,
        alignment_score=alignment_score,
        metadata={
            "answer_text": answer_text,
            "thread_context": thread_context,
            "graph_mode": graph_mode,
            "answer_quality": dict(quality_payload),
            "contributors": _normalize_contributors(contributors),
            "route_key": network_plan.get("route_key"),
            "llm_provider": item.get("llm_provider"),
            "llm_model": item.get("llm_model"),
            "goal_profile": goal_profile,
        },
    )


@dataclass
class GraphRuntimeDecision:
    mode: str = "full_run"
    matched_case_id: Optional[str] = None
    similarity: float = 0.0
    prior_answer: Optional[str] = None
    prior_case: Optional[dict[str, Any]] = None
    reason: str = "graph-disabled"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GraphMemoryRuntime:
    """Thin orchestration layer for graph-memory reuse decisions."""

    def __init__(
        self,
        store: MemoryGraphStore | None = None,
        retriever: MemoryGraphRetriever | None = None,
        *,
        store_path: str = "data/graph_memory/cases.jsonl",
        reuse_threshold: float = 0.92,
        refine_threshold: float = 0.78,
        min_similarity: float = 0.35,
    ) -> None:
        self.store = store or MemoryGraphStore(store_path)
        self.retriever = retriever or MemoryGraphRetriever(self.store)
        self._logger = logging.getLogger(__name__)
        self.reuse_threshold = reuse_threshold
        self.refine_threshold = refine_threshold
        self.min_similarity = min_similarity

    def process(self, item, thread_context: str | None = None) -> GraphRuntimeDecision:
        try:
            question = self.retriever.normalize_question(item)
            if thread_context is not None:
                question.thread_context = str(thread_context)
            if not (question.text or question.clean_text):
                return GraphRuntimeDecision(reason="empty-question")

            if not self.store.list_cases():
                return GraphRuntimeDecision(reason="empty-store")

            match = self.retriever.best_match(question, min_similarity=self.min_similarity)
            decision = decide_reuse(
                match,
                reuse_threshold=self.reuse_threshold,
                refine_threshold=self.refine_threshold,
            )

            prior_answer: Optional[str] = None
            prior_case: Optional[dict[str, Any]] = None
            if match is not None and decision.mode in {"reuse", "refine"}:
                prior_answer = match.case.answer_text or None
                prior_case = match.case.to_dict()

            if decision.mode == "reuse" and decision.matched_case_id:
                self.store.mark_reused(decision.matched_case_id)

            return GraphRuntimeDecision(
                mode=decision.mode,
                matched_case_id=decision.matched_case_id,
                similarity=decision.similarity,
                prior_answer=prior_answer,
                prior_case=prior_case,
                reason=decision.reason,
            )
        except Exception as exc:
            return GraphRuntimeDecision(reason=f"graph-runtime-error:{exc.__class__.__name__}")

    def remember_success(
        self,
        item,
        *,
        answer_text: str,
        thread_context: str | None = None,
        answer_quality: dict[str, Any] | None = None,
        contributors: list[dict[str, Any]] | None = None,
    ) -> MemoryCase | None:
        if not answer_text or not answer_text.strip():
            return None

        try:
            question = self.retriever.normalize_question(item)
            if thread_context is not None:
                question.thread_context = str(thread_context)
            saved_case = self.store.remember(
                question_text=question.text,
                clean_text=question.clean_text or question.text,
                intent=question.intent,
                why=question.why,
                thread_context=question.thread_context,
                answer_text=answer_text,
                answer_quality=dict(answer_quality or {}),
                contributors=list(contributors or []),
            )
            try:
                if _should_store_resonance_unit(item, answer_text, answer_quality):
                    unit = _build_resonance_unit(
                        item,
                        answer_text=answer_text,
                        thread_context=thread_context,
                        answer_quality=answer_quality,
                        contributors=contributors,
                    )
                    self.store.store_resonance_unit(unit)
            except Exception as exc:
                self._logger.debug("Failed to store ResonanceKnowledgeUnit: %s", exc)
            return saved_case
        except Exception as exc:
            self._logger.debug("Graph remember_success failed: %s", exc)
            return None
