"""Tool runtime with sandbox checks, retries, and audit logging."""

from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Dict

ToolCallable = Callable[[Dict[str, Any]], Dict[str, Any]]


class ToolRuntime:
    """Execute external tools with safety checks and observability."""

    def __init__(
        self,
        cognitive_state: Dict[str, Any],
        tool_registry: Dict[str, ToolCallable] | None = None,
        sandbox_mode: bool = True,
        default_timeout_s: float = 1.0,
        max_retries: int = 1,
        circuit_breaker_threshold: int = 3,
    ):
        self.cognitive_state = cognitive_state
        self.tool_registry = tool_registry or {}
        self.sandbox_mode = sandbox_mode
        self.default_timeout_s = default_timeout_s
        self.max_retries = max_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run tool action through sandbox checks and retry policy."""
        if self._is_circuit_open(action):
            self._audit(action, "blocked", "circuit_open")
            self._update_health(action, False, error_count=self._get_error_count(action), circuit_open=True)
            return {"status": "blocked", "reason": "circuit_open", "action": action}

        if action not in self.tool_registry:
            return {"status": "skipped", "reason": "tool_not_registered", "action": action}

        if self.sandbox_mode and not self._validate_payload(payload):
            self._audit(action, "blocked", "sandbox_validation_failed")
            self._increment_error_count(action)
            self._update_health(action, False, error_count=self._get_error_count(action))
            return {"status": "blocked", "reason": "sandbox_validation_failed", "action": action}

        tool = self.tool_registry[action]
        timeout_s = float(payload.get("timeout_s", self.default_timeout_s) or self.default_timeout_s)

        last_error = "unknown"
        for attempt in range(1, self.max_retries + 2):
            started = monotonic()
            try:
                result = tool(payload)
                elapsed = monotonic() - started
                if elapsed > timeout_s:
                    raise TimeoutError(f"timeout after {elapsed:.3f}s")

                self._audit(action, "ok", None, elapsed=elapsed, attempt=attempt)
                self._reset_error_count(action)
                self._update_health(action, True, error_count=0)
                return {
                    "status": "ok",
                    "action": action,
                    "result": result,
                    "elapsed_s": elapsed,
                    "attempt": attempt,
                }
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                self._audit(action, "error", last_error, attempt=attempt)

        self._increment_error_count(action)
        error_count = self._get_error_count(action)
        circuit_open = error_count >= self.circuit_breaker_threshold
        self._update_health(action, False, error_count=error_count, circuit_open=circuit_open)
        return {
            "status": "error",
            "action": action,
            "error": last_error,
            "error_count": error_count,
            "circuit_open": circuit_open,
        }

    def _validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Basic sandbox gate: block dangerous keys and oversized payloads."""
        blocked_keys = {"shell", "command", "exec", "subprocess"}
        if any(key in payload for key in blocked_keys):
            return False
        payload_size = len(str(payload))
        return payload_size <= 10_000

    def _is_circuit_open(self, action: str) -> bool:
        """Return whether circuit for a tool is open due to repeated failures."""
        return self._get_error_count(action) >= self.circuit_breaker_threshold

    def _increment_error_count(self, action: str) -> None:
        """Increment persistent error count for an action."""
        counts = self.cognitive_state.setdefault("tool_error_counts", {})
        counts[action] = int(counts.get(action, 0) or 0) + 1

    def _reset_error_count(self, action: str) -> None:
        """Reset persistent error count after success."""
        counts = self.cognitive_state.setdefault("tool_error_counts", {})
        counts[action] = 0

    def _get_error_count(self, action: str) -> int:
        """Read persistent error count for an action."""
        counts = self.cognitive_state.get("tool_error_counts", {})
        return int(counts.get(action, 0) or 0)

    def _audit(
        self,
        action: str,
        status: str,
        error: str | None,
        elapsed: float | None = None,
        attempt: int | None = None,
    ) -> None:
        """Append tool execution audit event to cognitive state."""
        audit_log = self.cognitive_state.setdefault("tool_audit_log", [])
        audit_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "status": status,
                "error": error,
                "elapsed_s": elapsed,
                "attempt": attempt,
            }
        )

    def _update_health(
        self,
        action: str,
        is_healthy: bool,
        error_count: int = 0,
        circuit_open: bool = False,
    ) -> None:
        """Track tool health snapshots by action name."""
        tool_health = self.cognitive_state.setdefault("tool_health", {})
        tool_health[action] = {
            "is_healthy": is_healthy,
            "error_count": error_count,
            "circuit_open": circuit_open,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
