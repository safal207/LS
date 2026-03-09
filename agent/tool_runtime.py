"""Tool runtime with adapters, sandbox checks, retries, and audit logging."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Dict, Mapping, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
import json

ToolCallable = Callable[[Dict[str, Any]], Dict[str, Any]]


class ToolAdapter(Protocol):
    """Contract for production-oriented tool integrations."""

    def name(self) -> str:
        """Return stable tool action name used in runtime routing."""

    def healthcheck(self) -> Dict[str, Any]:
        """Return adapter health details, including an `ok` boolean."""

    def execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool request and return structured result."""


class CallableToolAdapter:
    """Backward-compatible adapter wrapper for legacy callable tools."""

    def __init__(self, action_name: str, tool: ToolCallable):
        self._action_name = action_name
        self._tool = tool

    def name(self) -> str:
        return self._action_name

    def healthcheck(self) -> Dict[str, Any]:
        return {"ok": True, "source": "callable"}

    def execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._tool(request)


class HttpContextToolAdapter:
    """Simple HTTP adapter for retrieving external context payloads."""

    def __init__(self, action_name: str, base_url: str, timeout_s: float = 1.0):
        self._action_name = action_name
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def name(self) -> str:
        return self._action_name

    def healthcheck(self) -> Dict[str, Any]:
        return {"ok": bool(self.base_url), "base_url": self.base_url}

    def execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        query = request.get("query")
        event_sequence = request.get("event_sequence", [])
        if not query and event_sequence:
            query = event_sequence[-1].get("value")

        url = f"{self.base_url}/context"
        payload = json.dumps({"query": query, "event_count": len(event_sequence)}).encode("utf-8")
        req = urllib_request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urllib_request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
        except urllib_error.URLError as exc:
            raise RuntimeError(f"http_adapter_error: {exc}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}

        return {"status": "ok", "response": parsed}


class InMemoryDataToolAdapter:
    """Data adapter for deterministic reads/writes inside cognitive state."""

    def __init__(self, action_name: str, cognitive_state: Dict[str, Any], namespace: str = "tool_data"):
        self._action_name = action_name
        self._state = cognitive_state
        self.namespace = namespace

    def name(self) -> str:
        return self._action_name

    def healthcheck(self) -> Dict[str, Any]:
        return {"ok": True, "namespace": self.namespace}

    def execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        store = self._state.setdefault(self.namespace, {})
        op = request.get("op", "get")
        key = request.get("key")

        if op == "set":
            store[key] = request.get("value")
            return {"status": "ok", "op": "set", "key": key, "value": store[key]}

        return {"status": "ok", "op": "get", "key": key, "value": store.get(key)}


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
        audit_log_retention: int = 1000,
    ):
        self.cognitive_state = cognitive_state
        self.sandbox_mode = sandbox_mode
        self.default_timeout_s = default_timeout_s
        self.max_retries = max_retries
        self.audit_log_retention = max(1, int(audit_log_retention))

        adapters: Dict[str, ToolAdapter] = {}
        for action, tool in (tool_registry or {}).items():
            adapters[action] = CallableToolAdapter(action, tool)
        for action, adapter in (tool_adapters or {}).items():
            adapters[action] = adapter
        self.tool_adapters = adapters

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run tool action through sandbox checks and retry policy."""
        if self.is_circuit_open(action):
            self._audit(action, "blocked", "circuit_open")
            self._update_health(action, False, error_count=self._get_error_count(action), circuit_open=True)
            return {"status": "blocked", "reason": "circuit_open", "action": action}

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
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(adapter.execute, payload)
                    try:
                        result = future.result(timeout=timeout_s)
                    except FutureTimeoutError:
                        future.cancel()
                        elapsed = monotonic() - started
                        last_error = f"Tool execution timed out after {timeout_s}s"
                        self._audit(action, "timeout", last_error, elapsed=elapsed, attempt=attempt)
                        raise TimeoutError(last_error)

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

    def run_active_healthchecks(self) -> Dict[str, Dict[str, Any]]:
        """Run healthchecks for all registered adapters and persist snapshots."""
        health_results: Dict[str, Dict[str, Any]] = {}
        for action, adapter in self.tool_adapters.items():
            try:
                result = adapter.healthcheck()
                ok = bool(result.get("ok", False))
                health_results[action] = {"ok": ok, **result}
                self._update_health(action, ok, error_count=self._get_error_count(action), circuit_open=self.is_circuit_open(action))
            except Exception as exc:  # noqa: BLE001
                health_results[action] = {"ok": False, "error": str(exc)}
                self._update_health(action, False, error_count=self._get_error_count(action), circuit_open=self.is_circuit_open(action))
        self.cognitive_state["last_tool_healthcheck"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": health_results,
        }
        return health_results

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
        if len(audit_log) > self.audit_log_retention:
            del audit_log[:-self.audit_log_retention]

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
