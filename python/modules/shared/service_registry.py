from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Dict, Iterable, Set


@dataclass(frozen=True)
class ServiceEntry:
    name: str
    service: Any
    capabilities: Set[str] = field(default_factory=set)


class ServiceRegistry:
    """Lightweight runtime service registry for app-scoped singletons."""

    def __init__(self):
        self._services: Dict[str, ServiceEntry] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        service: Any,
        capabilities: Iterable[str] | None = None,
        replace: bool = False,
    ) -> None:
        if not name:
            raise ValueError("Service name must be non-empty")
        with self._lock:
            if name in self._services and not replace:
                raise KeyError(f"Service already registered: {name}")
            cap_set = set(capabilities or [])
            self._services[name] = ServiceEntry(name=name, service=service, capabilities=cap_set)

    def get(self, name: str, required_capability: str | None = None) -> Any:
        try:
            with self._lock:
                entry = self._services[name]
        except KeyError as exc:
            raise KeyError(f"Service not found: {name}") from exc

        if required_capability and required_capability not in entry.capabilities:
            raise PermissionError(
                f"Service '{name}' does not grant capability '{required_capability}'"
            )
        return entry.service

    def capabilities(self, name: str) -> Set[str]:
        with self._lock:
            if name not in self._services:
                raise KeyError(f"Service not found: {name}")
            return set(self._services[name].capabilities)

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._services

    def unregister(self, name: str) -> None:
        with self._lock:
            self._services.pop(name, None)

    def list_services(self) -> list[str]:
        with self._lock:
            return sorted(self._services.keys())
