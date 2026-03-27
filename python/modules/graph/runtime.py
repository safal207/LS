from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from .memory_store import MemoryGraphStore
from .models import MemoryCase
from .retriever import MemoryGraphRetriever
from .reuse import decide_reuse


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
            return self.store.remember(
                question_text=question.text,
                clean_text=question.clean_text or question.text,
                intent=question.intent,
                why=question.why,
                thread_context=question.thread_context,
                answer_text=answer_text,
                answer_quality=dict(answer_quality or {}),
                contributors=list(contributors or []),
            )
        except Exception:
            return None
