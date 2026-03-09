"""Tool runtime with adapters, sandbox checks, retries, and audit logging."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Dict, Mapping, Protocol

ToolCallable = Callable[[Dict[str, Any]], Dict[str, Any]]


class ToolAdapter(Protocol):
    """Contract for production tool adapters."""

    def name(self) -> str: ...

    def healthcheck(self) -> bool: ...

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...


class CallableToolAdapter:
    """Compatibility adapter to wrap legacy callables into ToolAdapter contract."""

    def __init__(self, action_name: str, tool: ToolCallable):
        self._action_name = action_name
        self._tool = tool

    def name(self) -> str:
        return self._action_name

    def healthcheck(self) -> bool:
        return True

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._tool(payload)


class ToolRuntime:
    """Execute external tools with safety checks and observability."""

    def __init__(
        self,
        cognitive_state: Dict[str, Any],
        tool_registry: Dict[str, ToolCallable] | None = None,
        tool_adapters: Mapping[str, ToolAdapter] | None = None,
        sandbox_mode: bool = True,
        default_timeout_s: float = 1.0,
        max_retries: int = 1,
        circuit_breaker_threshold: int = 3,
    ):
        self.cognitive_state = cognitive_state
        self.tool_registry = tool_registry or {}
        self.tool_adapters: Dict[str, ToolAdapter] = dict(tool_adapters or {})
        for action, tool in self.tool_registry.items():
            self.tool_adapters.setdefault(action, CallableToolAdapter(action, tool))
        self.sandbox_mode = sandbox_mode
        self.default_timeout_s = default_timeout_s
        self.max_retries = max_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold

        adapters: Dict[str, ToolAdapter] = {}
        for action, tool in (tool_registry or {}).items():
            adapters[action] = CallableToolAdapter(action, tool)
        for action, adapter in (tool_adapters or {}).items():
            adapters[action] = adapter
        self.tool_adapters = adapters

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run tool action through sandbox checks and retry policy."""
        adapter = self.tool_adapters.get(action)
        if adapter is None:
            return {"status": "skipped", "reason": "tool_not_registered", "action": action}

        if self._is_degraded(action):
            self._audit(action, "circuit_open", "tool_unhealthy_degraded")
            return {"status": "circuit_open", "reason": "tool_unhealthy_degraded", "action": action}

        if self.sandbox_mode and not self._validate_payload(payload):
            self._audit(action, "blocked", "sandbox_validation_failed")
            return {"status": "blocked", "reason": "sandbox_validation_failed", "action": action}

        timeout_s = float(payload.get("timeout_s", self.default_timeout_s) or self.default_timeout_s)

        last_error = "unknown"
        for attempt in range(1, self.max_retries + 2):
            started = monotonic()
            try:
                result = adapter.execute(payload)
                elapsed = monotonic() - started
                if elapsed > timeout_s:
                    raise TimeoutError(f"timeout after {elapsed:.3f}s")

                elapsed = monotonic() - started
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
                if "timed out" not in last_error:
                    self._audit(action, "error", last_error, attempt=attempt)

        self._increment_error_count(action)
        error_count = self._get_error_count(action)
        circuit_open = error_count >= self.circuit_breaker_threshold
        self._update_health(action, False, error_count=error_count, circuit_open=circuit_open)

        status = "timeout" if "timed out" in last_error else "error"
        return {
            "status": status,
            "action": action,
            "error": last_error,
            "error_count": error_count,
            "circuit_open": circuit_open,
        }

    def run_healthchecks(self, active: bool = True) -> Dict[str, bool]:
        """Run adapter health checks and persist snapshots; returns action->is_healthy."""
        if not active:
            current = self.cognitive_state.get("tool_health", {})
            if isinstance(current, dict):
                return {k: bool(v.get("is_healthy")) for k, v in current.items() if isinstance(v, dict)}
            return {}

        snapshots: Dict[str, bool] = {}
        for action, adapter in self.tool_adapters.items():
            is_healthy = False
            try:
                is_healthy = bool(adapter.healthcheck())
            except Exception:  # noqa: BLE001
                is_healthy = False
            self._update_health(action, is_healthy)
            snapshots[action] = is_healthy
        return snapshots

    def _is_degraded(self, action: str) -> bool:
        """Passive degradation gate based on last known health snapshot."""
        tool_health = self.cognitive_state.get("tool_health", {})
        if not isinstance(tool_health, dict):
            return False
        item = tool_health.get(action)
        if not isinstance(item, dict):
            return False
        return item.get("is_healthy") is False

    def _validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Basic sandbox gate: block dangerous keys and oversized payloads."""
        blocked_keys = {"shell", "command", "exec", "subprocess"}
        if any(key in payload for key in blocked_keys):
            return False
        payload_size = len(str(payload))
        return payload_size <= 10_000

    def is_circuit_open(self, action: str) -> bool:
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
