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


def _extract_graph_mode(item: dict[str, Any]) -> Any:
    graph_runtime = item.get("_graph_runtime") or {}
    return (
        item.get("_graph_mode")
        or item.get("graph_mode")
        or graph_runtime.get("mode")
    )


def _extract_quality_score(answer_quality: dict[str, Any] | None) -> float:
    quality_payload = answer_quality or {}
    return _as_float(
        quality_payload.get("overall")
        or quality_payload.get("score")
        or quality_payload.get("quality")
        or quality_payload.get("final_score"),
        0.0,
    )


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]
    if hasattr(value, "to_dict"):
        return _to_json_safe(value.to_dict())
    return str(value)


def _normalize_contributors(
    contributors: list[Any] | None,
) -> list[dict[str, Any] | str]:
    normalized: list[dict[str, Any] | str] = []
    for contributor in contributors or []:
        if hasattr(contributor, "to_dict"):
            normalized.append(_to_json_safe(contributor.to_dict()))
        elif isinstance(contributor, dict):
            normalized.append(_to_json_safe(contributor))
        else:
            normalized.append(str(contributor))
    return normalized


def _has_semantic_signal(item: dict[str, Any]) -> bool:
    intent = item.get("_intent") or item.get("intent")
    why = item.get("_why") or item.get("why")
    why_strategy = item.get("_why_strategy") or {}
    network_plan = item.get("_network_plan") or {}
    return any(
        [
            bool(str(intent).strip()) if intent is not None else False,
            bool(str(why).strip()) if why is not None else False,
            bool(why_strategy),
            bool(network_plan.get("route_key") or network_plan.get("goal_vector")),
        ]
    )


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

    graph_mode = _extract_graph_mode(item)
    if graph_mode == "reuse":
        return False

    if not _has_semantic_signal(item):
        return False

    resonance_score = _as_float(item.get("_resonance_score"), 0.0)
    overall = _extract_quality_score(answer_quality)

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
    quality_payload = answer_quality or {}
    graph_mode = _extract_graph_mode(item)
    goal_vector_raw = network_plan.get("goal_vector")

    if isinstance(goal_vector_raw, list):
        goal_vector = _to_json_safe(goal_vector_raw)
        goal_profile = None
    else:
        goal_vector = []
        goal_profile = _to_json_safe(goal_vector_raw)

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
            "answer_quality": _to_json_safe(dict(quality_payload)),
            "contributors": _normalize_contributors(contributors),
            "route_key": network_plan.get("route_key"),
            "llm_provider": item.get("llm_provider"),
            "llm_model": item.get("llm_model"),
            "goal_profile": goal_profile,
        },
    )


def _shorten_text(value: Any, *, limit: int = 220) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _short_causal_path(causal_path: list[dict[str, Any]]) -> str | None:
    if not causal_path:
        return None
    fragments: list[str] = []
    for step in causal_path[:2]:
        if not isinstance(step, dict):
            continue
        step_name = str(step.get("step") or "").strip()
        strategy = str(step.get("strategy") or "").strip()
        outcome = str(step.get("outcome") or "").strip()
        if not (step_name or strategy or outcome):
            continue
        left = ":".join([part for part in [step_name, strategy] if part])
        fragments.append("→".join([part for part in [left, outcome] if part]))
    return " | ".join(fragments) if fragments else None


def _build_resonance_hints(units: list[ResonanceKnowledgeUnit]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for unit in units:
        metadata = unit.metadata or {}
        answer_pattern = metadata.get("answer_pattern")
        if not answer_pattern:
            answer_pattern = metadata.get("answer_text")
        hint = {
            "intent": _shorten_text(unit.intent, limit=80),
            "why": _shorten_text(unit.why, limit=120),
            "route_key": _shorten_text(metadata.get("route_key"), limit=120),
            "causal_path": _short_causal_path(unit.causal_path),
            "answer_pattern": _shorten_text(answer_pattern, limit=220),
            "resonance_score": round(_as_float(unit.resonance_score, 0.0), 3),
            "alignment_score": round(_as_float(unit.alignment_score, 0.0), 3),
        }
        if any(value not in (None, "", []) for value in hint.values()):
            hints.append(hint)
    return hints


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


@dataclass
class ResonanceMemoryMetrics:
    hint_injection_calls: int = 0
    hint_injection_nonempty: int = 0
    hint_injection_errors: int = 0
    retrieval_empty_query: int = 0
    retrieval_miss: int = 0
    retrieval_hit: int = 0
    hint_count_total: int = 0
    units_saved: int = 0
    units_save_skipped: int = 0
    units_save_errors: int = 0
    _hint_resonance_score_sum: float = 0.0
    _hint_alignment_score_sum: float = 0.0
    _hint_score_count: int = 0

    def record_hint_injection_call(self) -> None:
        self.hint_injection_calls += 1

    def record_hint_injection_error(self) -> None:
        self.hint_injection_errors += 1

    def record_retrieval_empty_query(self) -> None:
        self.retrieval_empty_query += 1

    def record_retrieval_miss(self) -> None:
        self.retrieval_miss += 1

    def record_retrieval_hit(self, hints: list[dict[str, Any]]) -> None:
        self.retrieval_hit += 1
        self.hint_injection_nonempty += 1
        self.hint_count_total += len(hints)
        for hint in hints:
            resonance_score = _as_float(hint.get("resonance_score"), 0.0)
            alignment_score = _as_float(hint.get("alignment_score"), 0.0)
            self._hint_resonance_score_sum += resonance_score
            self._hint_alignment_score_sum += alignment_score
            self._hint_score_count += 1

    def record_unit_saved(self) -> None:
        self.units_saved += 1

    def record_unit_save_skipped(self) -> None:
        self.units_save_skipped += 1

    def record_unit_save_error(self) -> None:
        self.units_save_errors += 1

    def to_dict(self) -> dict[str, Any]:
        avg_hints_per_hit = (
            self.hint_count_total / self.retrieval_hit if self.retrieval_hit else 0.0
        )
        avg_hint_resonance_score = (
            self._hint_resonance_score_sum / self._hint_score_count
            if self._hint_score_count
            else 0.0
        )
        avg_hint_alignment_score = (
            self._hint_alignment_score_sum / self._hint_score_count
            if self._hint_score_count
            else 0.0
        )
        return {
            "hint_injection_calls": self.hint_injection_calls,
            "hint_injection_nonempty": self.hint_injection_nonempty,
            "hint_injection_errors": self.hint_injection_errors,
            "retrieval_empty_query": self.retrieval_empty_query,
            "retrieval_miss": self.retrieval_miss,
            "retrieval_hit": self.retrieval_hit,
            "hint_count_total": self.hint_count_total,
            "units_saved": self.units_saved,
            "units_save_skipped": self.units_save_skipped,
            "units_save_errors": self.units_save_errors,
            "avg_hints_per_hit": avg_hints_per_hit,
            "avg_hint_resonance_score": avg_hint_resonance_score,
            "avg_hint_alignment_score": avg_hint_alignment_score,
        }


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
        self._resonance_metrics = ResonanceMemoryMetrics()

    def get_resonance_metrics(self) -> dict[str, Any]:
        return self._resonance_metrics.to_dict()

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
                    self._resonance_metrics.record_unit_saved()
                else:
                    self._resonance_metrics.record_unit_save_skipped()
            except Exception as exc:
                self._resonance_metrics.record_unit_save_error()
                self._logger.debug("Failed to store ResonanceKnowledgeUnit: %s", exc)
            return saved_case
        except Exception as exc:
            self._logger.debug("Graph remember_success failed: %s", exc)
            return None

    def inject_resonance_hints(
        self,
        item: dict[str, Any],
        *,
        thread_context: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        self._resonance_metrics.record_hint_injection_call()
        try:
            question = self.retriever.normalize_question(item)
            if thread_context is not None:
                question.thread_context = str(thread_context)
            query_text = (question.clean_text or question.text or "").strip()
            if not query_text:
                self._resonance_metrics.record_retrieval_empty_query()
                item["_resonance_hints"] = []
                return []

            relevant_units = self.store.find_relevant_units(
                intent=question.intent or None,
                why=question.why or None,
                query_text=query_text,
                top_k=max(1, min(int(top_k or 1), 3)),
            )
            hints = _build_resonance_hints(relevant_units)
            if relevant_units:
                self._resonance_metrics.record_retrieval_hit(hints)
            else:
                self._resonance_metrics.record_retrieval_miss()
            item["_resonance_hints"] = hints
            return hints
        except Exception as exc:
            self._resonance_metrics.record_hint_injection_error()
            self._logger.debug("Graph inject_resonance_hints failed: %s", exc)
            item["_resonance_hints"] = []
            return []
