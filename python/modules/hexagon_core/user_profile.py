# -*- coding: utf-8 -*-
"""
UserProfileStore — долгосрочный профиль пользователя.

Отслеживает паттерны когнитивных режимов per user_id.
Позволяет системе начинать разговор уже с правильным предположением
о стиле мышления конкретного человека, не тратя первые сообщения на обнаружение.

Хранится в памяти процесса. Для персистентности — см. TODO ниже.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class UserSession:
    """Профиль одного пользователя."""
    user_id: str
    # Накопительные счётчики режимов: mode → кол-во встреч
    mode_counts: Dict[str, int] = field(default_factory=dict)
    # Последние N режимов (скользящее окно для учёта дрейфа)
    recent_modes: deque = field(default_factory=lambda: deque(maxlen=20))
    turn_count: int = 0
    last_mode: Optional[str] = None
    last_seen: float = field(default_factory=time.time)

    def record(self, mode: str) -> None:
        self.mode_counts[mode] = self.mode_counts.get(mode, 0) + 1
        self.recent_modes.append(mode)
        self.turn_count += 1
        self.last_mode = mode
        self.last_seen = time.time()

    def dominant_mode(self) -> Optional[str]:
        """Исторически доминирующий режим."""
        if not self.mode_counts:
            return None
        return max(self.mode_counts, key=self.mode_counts.__getitem__)

    def recent_dominant_mode(self) -> Optional[str]:
        """Доминирующий режим в скользящем окне (последние 20 ходов)."""
        if not self.recent_modes:
            return None
        counts: Dict[str, int] = {}
        for m in self.recent_modes:
            counts[m] = counts.get(m, 0) + 1
        return max(counts, key=counts.__getitem__)

    def dominant_confidence(self) -> float:
        """Уверенность в доминирующем режиме (0.0–1.0)."""
        if self.turn_count < 5:
            return 0.0
        top = max(self.mode_counts.values(), default=0)
        return round(top / self.turn_count, 3)


class UserProfileStore:
    """
    Хранилище профилей пользователей.

    Использование:
        store = UserProfileStore()
        store.record_turn("user_42", "deliberative")
        hint = store.get_starting_hint("user_42")
        # → "deliberative" если достаточно данных, иначе None
    """

    # Минимальное число ходов для надёжного хинта
    _MIN_TURNS = 5

    def __init__(self) -> None:
        self._profiles: Dict[str, UserSession] = {}

    def record_turn(self, user_id: str, mode: str) -> None:
        """Записывает режим текущего хода для пользователя."""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserSession(user_id=user_id)
        self._profiles[user_id].record(mode)

    def get_starting_hint(self, user_id: str) -> Optional[str]:
        """
        Возвращает предполагаемый режим для начала разговора с этим пользователем.
        None если данных недостаточно (< _MIN_TURNS ходов).
        Предпочитает recent_dominant_mode для учёта изменений стиля.
        """
        p = self._profiles.get(user_id)
        if not p or p.turn_count < self._MIN_TURNS:
            return None
        return p.recent_dominant_mode() or p.dominant_mode()

    def get_confidence(self, user_id: str) -> float:
        """Уверенность в хинте (0.0 если данных нет)."""
        p = self._profiles.get(user_id)
        return p.dominant_confidence() if p else 0.0

    def profile_summary(self, user_id: str) -> dict:
        """Полный срез профиля для observability."""
        p = self._profiles.get(user_id)
        if not p:
            return {"user_id": user_id, "known": False}
        return {
            "user_id":            user_id,
            "known":              True,
            "turn_count":         p.turn_count,
            "dominant_mode":      p.dominant_mode(),
            "recent_dominant":    p.recent_dominant_mode(),
            "confidence":         p.dominant_confidence(),
            "mode_counts":        dict(p.mode_counts),
            "last_mode":          p.last_mode,
        }

    def all_user_ids(self) -> List[str]:
        return list(self._profiles.keys())

    # TODO: add persist(path) / load(path) for JSONL-based long-term storage
