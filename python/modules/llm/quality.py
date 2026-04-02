# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


_RU_STOPWORDS = {
    "и",
    "в",
    "во",
    "на",
    "с",
    "со",
    "к",
    "ко",
    "по",
    "за",
    "из",
    "у",
    "о",
    "об",
    "от",
    "а",
    "но",
    "или",
    "что",
    "как",
    "почему",
    "зачем",
    "где",
    "когда",
    "чем",
    "это",
    "этот",
    "эта",
    "эти",
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "for",
    "in",
    "on",
}

_CAUSE_CUES = (
    "потому что",
    "так как",
    "поскольку",
    "because",
    "since",
    "due to",
    "из-за",
)

_TECH_TERMS = {
    "node.js",
    "nodejs",
    "react",
    "postgresql",
    "postgres",
    "python",
    "java",
    "javascript",
    "typescript",
    "go",
    "golang",
    "rust",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "redis",
    "kafka",
    "graphql",
    "rest",
    "fastapi",
    "django",
    "next.js",
    "nextjs",
    "vue",
    "angular",
    "spring",
}

_TRUNCATION_CUES = (
    " и ",
    " или ",
    " но ",
    " because ",
    " however ",
    " moreover ",
)


@dataclass
class LLMQualityAssessment:
    adequacy: float
    relevance: float
    thread_relevance: float
    coherence: float
    hallucination_risk: float
    overall: float
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9_+.-]+", text.lower())


def _meaningful_tokens(text: str) -> list[str]:
    return [token for token in _tokens(text) if token not in _RU_STOPWORDS and len(token) > 1]


def _overlap(a: Iterable[str], b: Iterable[str]) -> float:
    a_set = set(a)
    b_set = set(b)
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / max(1, len(a_set))


def _cause_cue_score(answer: str) -> float:
    lower = answer.lower()
    return 1.0 if any(cue in lower for cue in _CAUSE_CUES) else 0.0


def _structure_score(answer: str) -> float:
    text = answer.strip()
    if not text:
        return 0.0
    score = 0.45
    if text[-1] in ".!?:":
        score += 0.25
    if len(text.split()) >= 8:
        score += 0.15
    if any(sep in text for sep in (";", "\n", " - ", "•", "- ")):
        score += 0.1
    if any(cue in text.lower() for cue in _TRUNCATION_CUES):
        score -= 0.1
    if re.search(r"\b\w+-\s*$", text):
        score -= 0.15
    return _clamp(score)


def _specificity_risk(question: str, answer: str, thread_context: str | None = None) -> float:
    q_tokens = set(_meaningful_tokens(question))
    t_tokens = set(_meaningful_tokens(thread_context or question))
    a_tokens = _meaningful_tokens(answer)
    named_entities = [token for token in a_tokens if re.search(r"[A-ZА-Я][a-zа-я0-9]+", token)]
    digits = re.findall(r"\d+", answer)
    grounded_overlap = len(set(a_tokens) & (q_tokens | t_tokens))
    risk = 0.15
    risk += min(0.35, 0.06 * len(named_entities))
    risk += min(0.20, 0.05 * len(digits))
    risk -= min(0.20, 0.04 * grounded_overlap)
    if len(a_tokens) < 8:
        risk += 0.10
    if "?" in answer:
        risk += 0.05
    return _clamp(risk)


def _topic_grounding(question: str, answer: str) -> float:
    q_lower = question.lower()
    a_lower = answer.lower()
    if not any(marker in q_lower for marker in ("stack", "стек", "технолог", "tech", "framework", "backend")):
        return 0.0
    matches = sum(1 for term in _TECH_TERMS if term in a_lower)
    return _clamp(matches / 3.0)


def _intent_alignment(question: str, answer: str) -> float:
    q_lower = question.lower()
    a_lower = answer.lower()
    score = 0.0

    if any(marker in q_lower for marker in ("почему", "why", "зачем")):
        if any(cue in a_lower for cue in _CAUSE_CUES):
            score += 0.45
        if any(marker in a_lower for marker in ("выбрал", "выбрали", "решил", "решила", "because", "из-за")):
            score += 0.2

    if any(marker in q_lower for marker in ("как", "how", "чем")):
        if any(marker in a_lower for marker in ("шаг", "process", "подход", "algorithm", "workflow", "план")):
            score += 0.2

    if any(marker in q_lower for marker in ("что", "what", "опиши", "describe")):
        if len(answer.split()) >= 8:
            score += 0.15

    return _clamp(score)


def _question_intent(question: str) -> str:
    q_lower = question.lower()
    if any(marker in q_lower for marker in ("почему", "why", "зачем")):
        return "why"
    if any(marker in q_lower for marker in ("как", "how", "чем")):
        return "how"
    if any(marker in q_lower for marker in ("что", "what", "опиши", "describe")):
        return "what"
    return "general"


def evaluate_llm_answer_quality(
    question: str,
    answer: str,
    thread_context: str | None = None,
) -> LLMQualityAssessment:
    if not answer.strip():
        return LLMQualityAssessment(
            adequacy=0.0,
            relevance=0.0,
            thread_relevance=0.0,
            coherence=0.0,
            hallucination_risk=1.0,
            overall=0.0,
            notes=["empty-answer"],
        )

    question_terms = _meaningful_tokens(question)
    answer_terms = _meaningful_tokens(answer)
    thread_terms = _meaningful_tokens(thread_context or question)
    intent = _question_intent(question)

    lexical_overlap = _clamp(_overlap(question_terms, answer_terms))
    thread_overlap = _clamp(_overlap(thread_terms, answer_terms))
    cause_score = _cause_cue_score(answer)
    structure = _structure_score(answer)
    length = len(answer_terms)
    topic_grounding = _topic_grounding(question, answer)
    intent_alignment = _intent_alignment(question, answer)

    relevance = _clamp(
        0.35 * lexical_overlap
        + 0.25 * cause_score
        + 0.20 * intent_alignment
        + 0.20 * topic_grounding
    )
    thread_relevance = _clamp(
        0.40 * thread_overlap
        + 0.25 * cause_score
        + 0.20 * intent_alignment
        + 0.15 * topic_grounding
    )

    if intent == "why":
        ideal = 0.35 if length < 12 else 0.65 if length < 40 else 0.55
        adequacy = 0.35 + 0.35 * cause_score + 0.3 * structure
        adequacy = max(adequacy, ideal)
    elif intent == "how":
        adequacy = 0.30 + 0.25 * cause_score + 0.45 * structure
    elif intent == "what":
        adequacy = 0.25 + 0.20 * cause_score + 0.55 * structure
    else:
        adequacy = 0.30 + 0.15 * cause_score + 0.55 * structure

    adequacy = _clamp(adequacy)
    coherence = _clamp(0.65 * structure + 0.35 * min(1.0, len(answer.split()) / 18.0))
    hallucination_risk = _specificity_risk(question, answer, thread_context=thread_context)

    overall = _clamp(
        0.30 * adequacy
        + 0.30 * relevance
        + 0.20 * thread_relevance
        + 0.20 * coherence
        - 0.20 * hallucination_risk
    )

    notes: list[str] = []
    if relevance < 0.35:
        notes.append("low-question-overlap")
    if thread_relevance < 0.35:
        notes.append("low-thread-alignment")
    if coherence < 0.45:
        notes.append("weak-structure")
    if hallucination_risk > 0.55:
        notes.append("high-specificity-risk")
    if not notes:
        notes.append("balanced")

    return LLMQualityAssessment(
        adequacy=round(adequacy, 3),
        relevance=round(relevance, 3),
        thread_relevance=round(thread_relevance, 3),
        coherence=round(coherence, 3),
        hallucination_risk=round(hallucination_risk, 3),
        overall=round(overall, 3),
        notes=notes,
    )
