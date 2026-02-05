from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Dict, Any
import re
import time


class ModeA:
    """
    Fast Mode (A): reactive, shallow responses.

    Principles:
    - No reasoning chains
    - No complex explanations
    - No context mutation
    - Best-effort, low latency
    """

    def __init__(self) -> None:
        self._facts = {
            "pi": "3.14159",
            "e": "2.71828",
        }
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_max = 128
        self._load_shed_threshold = 0.8

    def execute(self, input_data: str, context: Dict[str, Any], system_load: float = 0.0) -> Dict[str, Any]:
        """
        Execute a fast response.

        Returns:
            dict with keys: answer, mode, source, timestamp
        """
        key = self._cache_key(input_data)
        cached = self._cache_get(key)
        if cached is not None:
            return {
                "answer": cached,
                "mode": "A",
                "source": "cache",
                "timestamp": time.time(),
            }

        load_shed = system_load >= self._load_shed_threshold
        answer = self._handle_fast(input_data, load_shed=load_shed)
        if key:
            self._cache_set(key, answer)
        return {
            "answer": answer,
            "mode": "A",
            "source": "fast",
            "timestamp": time.time(),
        }

    def _handle_fast(self, input_data: str, *, load_shed: bool = False) -> str:
        text = (input_data or "").strip()
        lower = text.lower()

        if not text:
            return ""

        if self._is_greeting(lower):
            return "hello"

        if self._is_thanks(lower):
            return "you are welcome"

        if self._is_number(text):
            return text

        if lower.startswith("echo "):
            return text[5:].strip()

        if not load_shed:
            if lower.startswith("upper "):
                return text[6:].strip().upper()

            if lower.startswith("lower "):
                return text[6:].strip().lower()

            if lower.startswith("len "):
                return str(len(text[4:].strip()))

            if lower.startswith("rev "):
                return text[4:].strip()[::-1]

            if lower in {"time", "now"}:
                return datetime.now().strftime("%H:%M:%S")

            if lower in {"date", "today"}:
                return datetime.now().strftime("%Y-%m-%d")

        if lower in self._facts:
            return self._facts[lower]

        # Default fast reply: short echo-style response
        return text if len(text) <= 80 else text[:77] + "..."

    def _cache_key(self, input_data: str) -> str:
        return (input_data or "").strip().lower()

    def _cache_get(self, key: str) -> str | None:
        if not key:
            return None
        value = self._cache.get(key)
        if value is None:
            return None
        self._cache.move_to_end(key)
        return value

    def _cache_set(self, key: str, value: str) -> None:
        if not key:
            return
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    def _is_number(self, text: str) -> bool:
        return bool(re.fullmatch(r"[+-]?\\d+(?:\\.\\d+)?", text))

    def _is_greeting(self, lower: str) -> bool:
        return lower in {"hi", "hello", "hey", "yo"}

    def _is_thanks(self, lower: str) -> bool:
        return lower in {"thanks", "thank you", "thx"}
