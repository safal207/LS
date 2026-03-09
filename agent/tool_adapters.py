"""Concrete ToolAdapter implementations for production-like integrations."""

from __future__ import annotations

import json
from time import sleep
from typing import Any, Callable, Dict
from urllib.error import URLError
from urllib.request import Request, urlopen


class HTTPContextAdapter:
    """Adapter for retrieving external context over HTTP."""

    def __init__(
        self,
        base_url: str,
        health_path: str = "/health",
        default_path: str = "/context",
        timeout_s: float = 2.0,
        http_client: Callable[..., Dict[str, Any]] | None = None,
        max_retries: int = 2,
        backoff_base_s: float = 0.05,
    ):
        self.base_url = base_url.rstrip("/")
        self.health_path = health_path
        self.default_path = default_path
        self.timeout_s = timeout_s
        self.http_client = http_client
        self.max_retries = max(0, int(max_retries))
        self.backoff_base_s = max(0.0, float(backoff_base_s))

    def name(self) -> str:
        return "retrieve_context"

    def healthcheck(self) -> bool:
        try:
            data = self._request(self.health_path, {"probe": True})
            return bool(data.get("ok", True))
        except Exception:  # noqa: BLE001
            return False

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        query = payload.get("query") or payload.get("event_sequence") or []
        path = str(payload.get("path", self.default_path))
        return self._request(path, {"query": query})

    def _request(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if self.http_client is not None:
                    return self.http_client(base_url=self.base_url, path=path, body=body, timeout_s=self.timeout_s)

                raw = json.dumps(body).encode("utf-8")
                req = Request(
                    f"{self.base_url}{path}",
                    data=raw,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=self.timeout_s) as response:  # noqa: S310
                    return json.loads(response.read().decode("utf-8") or "{}")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._is_retryable_error(exc) or attempt >= self.max_retries:
                    break
                sleep(self.backoff_base_s * (2**attempt))

        raise RuntimeError(f"http_context_error: {last_error}") from last_error

    def _is_retryable_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        transient_markers = ("timeout", "tempor", "connection reset", "refused", "unavailable")
        return isinstance(exc, URLError) or any(marker in message for marker in transient_markers)



class DataAdapter:
    """Simple structured data adapter for get/set/delete operations."""

    def __init__(self, store: Dict[str, Any] | None = None):
        self.store = store if store is not None else {}

    def name(self) -> str:
        return "data_adapter"

    def healthcheck(self) -> bool:
        return isinstance(self.store, dict)

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        operation = str(payload.get("operation", "get"))
        key = str(payload.get("key", ""))

        if operation == "set":
            self.store[key] = payload.get("value")
            return {"ok": True, "operation": operation, "key": key}
        if operation == "delete":
            existed = key in self.store
            self.store.pop(key, None)
            return {"ok": True, "operation": operation, "key": key, "existed": existed}
        if operation == "list":
            return {"ok": True, "operation": operation, "keys": sorted(self.store.keys())}

        return {"ok": True, "operation": "get", "key": key, "value": self.store.get(key)}
