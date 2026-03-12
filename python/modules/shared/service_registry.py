from __future__ import annotations

from typing import Any, Dict


class ServiceRegistry:
    """Lightweight runtime service registry for app-scoped singletons."""

    def __init__(self):
        self._services: Dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        if not name:
            raise ValueError("Service name must be non-empty")
        if name in self._services:
            raise KeyError(f"Service already registered: {name}")
        self._services[name] = service

    def get(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise KeyError(f"Service not found: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self._services

    def unregister(self, name: str) -> None:
        self._services.pop(name, None)
