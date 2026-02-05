from __future__ import annotations

from typing import Dict, Any
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

    def execute(self, input_data: str, context: Dict[str, Any], system_load: float = 0.0) -> Dict[str, Any]:
        """
        Execute a fast response.

        Returns:
            dict with keys: answer, mode, source, timestamp
        """
        answer = self._handle_fast(input_data)
        return {
            "answer": answer,
            "mode": "A",
            "source": "fast",
            "timestamp": time.time(),
        }

    def _handle_fast(self, input_data: str) -> str:
        text = (input_data or "").strip()
        lower = text.lower()

        if lower.startswith("echo "):
            return text[5:].strip()

        if lower.startswith("upper "):
            return text[6:].strip().upper()

        if lower.startswith("lower "):
            return text[6:].strip().lower()

        if lower in self._facts:
            return self._facts[lower]

        if not text:
            return ""

        # Default fast reply: short echo-style response
        return text if len(text) <= 80 else text[:77] + "..."
