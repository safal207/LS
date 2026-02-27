from __future__ import annotations

from typing import Callable

REWRITE_PROMPT = """Rewrite the following user question to make it more specific, detailed and semantically rich for searching in a technical knowledge base.  
Preserve the original intent and language.  
Return **only** the rewritten query, without any explanations, quotes or prefixes.

Question: {question}"""


def rewrite_query(
    question: str,
    llm_handler: Callable[[str], str] | None = None,
) -> str:
    """
    Переписывает вопрос для улучшения векторного поиска.
    Если llm_handler не передан или упал — возвращает оригинал.
    """
    if not question or not question.strip():
        return question

    if llm_handler is None:
        return question

    try:
        prompt = REWRITE_PROMPT.format(question=question)
        rewritten = llm_handler(prompt).strip()
        return rewritten if rewritten else question
    except Exception:
        return question
