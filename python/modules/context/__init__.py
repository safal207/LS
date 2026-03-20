"""Conversation context anchoring — pins session facts for retrieval.

Usage::

    from context import ConversationAnchor, get_relevant_items

    anchor = ConversationAnchor()
    anchor.add("Сделал аудит их базы данных — нашёл 12 медленных запросов", priority=5)
    anchor.add("Оптимизировал индексы, ускорил выборку с 4s до 0.2s", priority=5)
    anchor.add("Работал с PostgreSQL 3 года", priority=3)

    relevant = get_relevant_items(anchor, "Почему выбрали такой подход?")
    # [AnchorItem(text="Оптимизировал индексы ...", priority=5), ...]
"""

from .conversation_anchor import AnchorItem, ConversationAnchor, get_relevant_items

__all__ = ["AnchorItem", "ConversationAnchor", "get_relevant_items"]
