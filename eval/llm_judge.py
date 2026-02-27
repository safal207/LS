from __future__ import annotations

import json
import re
from typing import Callable

JUDGE_PROMPT = """You are an expert evaluator for a RAG system.
Given a question and retrieved context, rate the relevance on a scale of 1-10.
Return ONLY a JSON object: {{"relevance": <int>, "hallucination_risk": <int>, "reasoning": "<one sentence>"}}

Question: {question}
Context: {context}"""


def judge_response(
    question: str,
    context: str,
    llm_handler: Callable[[str], str],
) -> dict[str, int | str]:
    if not context.strip():
        return {"relevance": 0, "hallucination_risk": 10, "reasoning": "No context provided"}

    try:
        raw = llm_handler(JUDGE_PROMPT.format(question=question, context=context))
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"relevance": 0, "hallucination_risk": 10, "reasoning": "Parse error"}
    except Exception:
        return {"relevance": 0, "hallucination_risk": 10, "reasoning": "Judge failed"}
