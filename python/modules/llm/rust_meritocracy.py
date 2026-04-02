from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger(__name__)

try:
    import ghostgpt_core as _ghostgpt_core  # type: ignore
except Exception:
    _ghostgpt_core = None


class RustMeritocracyBridge:
    def __init__(self) -> None:
        self._core = _ghostgpt_core
        self.available = bool(
            self._core is not None and hasattr(self._core, "meritocracy_select_json")
        )

    def select_winner(
        self,
        *,
        question: str,
        thread_context: str,
        candidates: list[dict[str, Any]],
        policy: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.available:
            return None
        try:
            payload = self._core.meritocracy_select_json(
                question,
                thread_context,
                json.dumps(candidates, ensure_ascii=False),
                json.dumps(policy, ensure_ascii=False),
            )
            if not payload:
                return None
            return json.loads(payload)
        except Exception as exc:
            logger.debug("rust meritocracy bridge failed: %s", exc)
            return None


_BRIDGE = RustMeritocracyBridge()


def rust_meritocracy_select(
    *,
    question: str,
    thread_context: str,
    candidates: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any] | None:
    return _BRIDGE.select_winner(
        question=question,
        thread_context=thread_context,
        candidates=candidates,
        policy=policy,
    )


def rust_meritocracy_available() -> bool:
    return bool(_BRIDGE.available)
