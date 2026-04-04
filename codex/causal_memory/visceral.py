# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from collections import deque

class VisceralMemory:
    """Висцеральная память — слой телесных сигналов перегрузки и разрешения."""

    def __init__(self, *, history_size: int = 500) -> None:
        self.phantom_pain: float = 0.0
        self.resolution_strength: float = 0.0
        self.last_trigger_intensity: float = 0.0
        self.history: deque[dict[str, float | str]] = deque(maxlen=history_size)

    def record_pain(self, intensity: float) -> None:
        self.phantom_pain = min(1.0, self.phantom_pain + intensity)
        self.last_trigger_intensity = max(0.0, intensity)
        self.history.append({
            "event": "pain",
            "intensity": self.last_trigger_intensity,
            "ts": time.time()
        })

    def resolve(self, *, strength: float = 0.25) -> None:
        self.phantom_pain = max(0.0, self.phantom_pain - (strength * 1.2))
        self.resolution_strength = min(1.0, self.resolution_strength + strength)
        self.history.append({
            "event": "resolve",
            "intensity": strength,
            "ts": time.time()
        })

    @property
    def is_painful(self) -> bool:
        return self.phantom_pain > 0.3

    def get_influence(self) -> float:
        return min(1.0, (self.phantom_pain * 0.5) + (self.last_trigger_intensity * 0.3))

    def compact_history(self) -> int:
        """Аггрегирует близкие события: delta_ts < 300 сек и intensity diff < 0.1 → объединить в одно."""
        if len(self.history) < 50:
            return 0

        compacted = 0
        new_history = deque(maxlen=self.history.maxlen)
        i = 0
        history_list = list(self.history)
        while i < len(history_list):
            current = history_list[i]
            if i + 1 < len(history_list):
                next_event = history_list[i + 1]
                ts_diff = next_event.get("ts", 0) - current.get("ts", 0)
                intensity_diff = abs(next_event.get("intensity", 0) - current.get("intensity", 0))
                if ts_diff < 300 and intensity_diff < 0.1 and current.get("event") == next_event.get("event"):
                    # Аггрегируем
                    avg_intensity = (current["intensity"] + next_event["intensity"]) / 2
                    aggregated = {
                        "event": current["event"],
                        "intensity": avg_intensity,
                        "aggregated": True,
                        "count": 2,
                        "ts": current["ts"],
                    }
                    new_history.append(aggregated)
                    compacted += 1
                    i += 2  # пропускаем следующий
                    continue
            new_history.append(current)
            i += 1

        self.history = new_history
        return compacted
