from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional

from shared.interview_schema import InterviewUtterance, ensure_interview_item

from .memory_store import MemoryGraphStore
from .models import MemoryCase, NetworkQuestion, RetrievedCase


def _tokenize(text: str) -> set[str]:
    return {token.strip(".,!?;:()[]{}\"'").lower() for token in text.split() if token.strip()}


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def _sequence_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left.lower(), b=right.lower()).ratio()


def compute_question_similarity(question: NetworkQuestion, case: MemoryCase) -> tuple[float, str]:
    clean_text = question.clean_text or question.text
    target_text = case.clean_text or case.question_text
    jaccard = _jaccard_similarity(clean_text, target_text)
    sequence = _sequence_similarity(clean_text, target_text)
    similarity = round((0.6 * jaccard) + (0.4 * sequence), 3)
    reason = f"jaccard={jaccard:.3f}, sequence={sequence:.3f}"
    return similarity, reason


class MemoryGraphRetriever:
    def __init__(self, store: MemoryGraphStore) -> None:
        self.store = store

    def normalize_question(self, payload) -> NetworkQuestion:
        if isinstance(payload, NetworkQuestion):
            return payload
        if isinstance(payload, InterviewUtterance):
            item = payload.to_item()
        else:
            item = ensure_interview_item(payload, default_source="graph")
        text = str(item.get("text", ""))
        clean_text = str(item.get("clean_text") or item.get("_clean_text") or text)
        intent = item.get("intent") or item.get("_intent")
        why = item.get("why") or item.get("_why")
        strategy = item.get("why_strategy") or item.get("_why_strategy")
        thread_context = item.get("thread_context") or item.get("context")
        return NetworkQuestion(
            text=text,
            clean_text=clean_text,
            intent=str(intent) if intent is not None else None,
            why=str(why) if why is not None else None,
            strategy=dict(strategy) if isinstance(strategy, dict) else None,
            thread_context=str(thread_context) if thread_context is not None else None,
        )

    def find_similar(
        self,
        payload,
        *,
        top_k: int = 3,
        min_similarity: float = 0.35,
    ) -> list[RetrievedCase]:
        question = self.normalize_question(payload)
        scored: list[RetrievedCase] = []
        for case in self.store.list_cases():
            similarity, reason = compute_question_similarity(question, case)
            if similarity >= min_similarity:
                scored.append(RetrievedCase(case=case, similarity=similarity, reason=reason))
        scored.sort(key=lambda item: item.similarity, reverse=True)
        return scored[:top_k]

    def best_match(self, payload, *, min_similarity: float = 0.35) -> Optional[RetrievedCase]:
        matches = self.find_similar(payload, top_k=1, min_similarity=min_similarity)
        return matches[0] if matches else None
