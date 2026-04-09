# -*- coding: utf-8 -*-
"""ConversationAnchor — session-level experience/fact store for the operator runtime.

The anchor holds short, high-value facts about the operator's real experience.
During each question, ``get_relevant_items`` returns the most relevant facts so
the system can prompt: "you have relevant experience — use it".

Why this exists
---------------
Under stress, operators forget their own experience.
The anchor acts as a working-memory prosthetic: it surfaces the right fact at
the right moment without the operator having to remember it.

Usage::

    anchor = ConversationAnchor()

    # Load before the operator session
    anchor.add("Сделал аудит базы данных — 12 медленных запросов", type="db", priority=5)
    anchor.add("Оптимизировал индексы: с 4s до 0.2s", type="perf", priority=5)
    anchor.add("Работал с PostgreSQL 3 года", type="tech", priority=3)

    # During each question
    relevant = get_relevant_items(anchor, "почему вы используете индексы?")
    for item in relevant:
        print(item.text)
    # → "Оптимизировал индексы: с 4s до 0.2s"

Scoring
-------
``get_relevant_items`` scores each anchor item by:
1. Word overlap between question and item text  (+1 per shared word)
2. Item priority                                (+priority)
Returns top-k by combined score.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Strip common stop-words before overlap scoring
_STOP_RU = frozenset({
    "а", "в", "во", "да", "за", "и", "к", "на", "не", "но", "о", "от",
    "по", "при", "с", "со", "у", "я", "мы", "вы", "он", "она", "они",
    "это", "как", "что", "кто", "где", "когда", "если", "то", "же",
    "вот", "всё", "все", "из", "до", "бы", "ли", "ни", "уже",
    "ваш", "ваши", "вашем", "вашего", "мой", "мои", "моего",
    "для", "об", "про", "через", "бы", "такое", "такой",
})
_STOP_EN = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "have", "has", "had", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "and", "or", "but", "nor", "so", "yet", "both", "either",
    "i", "you", "he", "she", "it", "we", "they", "me", "him",
    "us", "them", "my", "your", "his", "her", "its", "our", "their",
    "this", "that", "these", "those", "what", "which", "who", "how",
    "why", "when", "where",
})
_STOP = _STOP_RU | _STOP_EN

_WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.I)


def _tokenize(text: str) -> frozenset:
    return frozenset(
        w for w in _WORD_RE.findall(text.lower())
        if w not in _STOP and len(w) > 2
    )


@dataclass
class AnchorItem:
    """A single experience/fact record.

    Attributes:
        text:     Short description (1–2 sentences, first-person preferred).
        type:     Category tag: "tech" | "perf" | "db" | "arch" | "people" | "fact"
        priority: 1–5, higher = more important.  Default 3.
        tags:     Optional extra keyword tags for scoring boost.
    """
    text:     str
    type:     str = "fact"
    priority: int = 3
    tags:     List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.priority = max(1, min(5, int(self.priority)))


@dataclass
class ConversationAnchor:
    """Session-level experience store.

    Thread-safe for reads; single-writer assumed (call ``add`` from one thread).
    """
    items: List[AnchorItem] = field(default_factory=list)

    def add(
        self,
        text: str,
        type: str = "fact",
        priority: int = 3,
        tags: Optional[List[str]] = None,
    ) -> "ConversationAnchor":
        """Add an experience item.  Returns self for chaining."""
        if not text or not text.strip():
            return self
        self.items.append(AnchorItem(
            text=text.strip(),
            type=type,
            priority=priority,
            tags=tags or [],
        ))
        logger.debug("Anchor: added [%s p=%d] %r", type, priority, text[:60])
        return self

    def add_many(self, entries: List[dict]) -> "ConversationAnchor":
        """Bulk add.  Each entry: ``{"text": ..., "type": ..., "priority": ...}``."""
        for e in entries:
            self.add(**e)
        return self

    def clear(self) -> None:
        self.items.clear()

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"ConversationAnchor({len(self.items)} items)"


def get_relevant_items(
    anchor: ConversationAnchor,
    text: str,
    top_k: int = 2,
    min_score: int = 0,
) -> List[AnchorItem]:
    """Return up to *top_k* anchor items most relevant to *text*.

    Scoring per item:
        word_overlap (shared meaningful words)  × 2
        + item.priority
        + tag match bonus (+2 per tag word found in text)

    Args:
        anchor:    ConversationAnchor instance.
        text:      Current question / utterance.
        top_k:     Maximum number of items to return.
        min_score: Exclude items with score <= this (default 0 = no filter).

    Returns:
        List of :class:`AnchorItem` sorted by score descending.
    """
    if not anchor.items or not text:
        return []

    query_tokens = _tokenize(text)
    if not query_tokens:
        # fallback: return top-k by priority
        return sorted(anchor.items, key=lambda x: x.priority, reverse=True)[:top_k]

    scored: List[tuple] = []
    for item in anchor.items:
        item_tokens = _tokenize(item.text)
        overlap = len(query_tokens & item_tokens) * 2
        tag_bonus = sum(
            1 for tag in item.tags
            if any(t in query_tokens for t in _tokenize(tag))
        ) * 2
        score = overlap + item.priority + tag_bonus
        if score > min_score:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def format_anchor_block(items: List[AnchorItem]) -> str:
    """Format relevant items as a compact prompt block."""
    if not items:
        return ""
    lines = "\n".join(f"- {item.text}" for item in items)
    return f"Используй контекст, если уместно:\n{lines}"
