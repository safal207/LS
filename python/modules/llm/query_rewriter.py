from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """Rewrite the following technical question to improve vector search recall in a knowledge base.
Make it more concrete, include relevant technical terms if they are missing, but keep the rewritten query concise and natural.
Preserve original language and intent.
Return ONLY the rewritten question — no quotes, no explanations, no prefixes, no additional text.

Question: {question}"""

MAX_REWRITTEN_LENGTH = 300


def rewrite_query(
    question: str,
    llm_handler: Callable[[str], str] | None = None,
) -> str:
    """
    Переписывает вопрос для улучшения векторного поиска.
    Если llm_handler не передан, упал или вернул пустую строку — возвращает оригинал.

    Returns:
        str: переписанный вопрос или оригинал при любом сбое.
    """
    if not question or not question.strip():
        return question

    if llm_handler is None:
        return question

    try:
        prompt = REWRITE_PROMPT.format(question=question)
        rewritten = llm_handler(prompt).strip()

        if not rewritten:
            return question

        if len(rewritten) > MAX_REWRITTEN_LENGTH:
            logger.warning("Rewritten query too long (%d chars), falling back", len(rewritten))
            return question

        if rewritten != question:
            logger.debug("Query rewritten: %r → %r", question, rewritten)
        return rewritten
    except Exception as exc:
        logger.debug("Query rewrite failed: %s", str(exc), exc_info=True)
        return question
