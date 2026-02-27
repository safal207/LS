from __future__ import annotations

import json
import re
from typing import Callable

JUDGE_PROMPT = """You are an expert evaluator for a RAG system.
Evaluate ONLY based on how well the provided context directly answers the question.
Ignore your own knowledge — judge only using the given context.

Relevance scale:
10 — context fully and precisely answers the question, no missing key information
 8-9 — context contains most important facts, minor details may be missing
 5-7 — context partially relevant, answers some aspects but misses main point
 1-4 — context mentions question tangentially or contains unrelated information
 0 — completely irrelevant or empty

Hallucination risk (if model were to generate answer ONLY from this context):
10 — very high risk (almost no useful info -> model will hallucinate)
 1 — very low risk (context fully grounds answer)

Return ONLY valid JSON, no other text:
{{"relevance": <int 0-10>, "hallucination_risk": <int 0-10>, "reasoning": "<one sentence in English>"}}

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
        matches = re.findall(r"(\{.*?\})", raw, re.DOTALL | re.MULTILINE)
        if matches:
            return json.loads(matches[-1])
        return {"relevance": 0, "hallucination_risk": 10, "reasoning": "Parse error"}
    except Exception:
        return {"relevance": 0, "hallucination_risk": 10, "reasoning": "Judge failed"}
