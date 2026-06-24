from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from .contracts import RouteDecision
from .protocols import RoutingAdapter


class AdapterRegistryError(RuntimeError):
    """Base error for adapter registry operations."""


class DuplicateAdapterError(AdapterRegistryError):
    """Raised when an adapter name is registered twice."""


class UnknownAdapterError(AdapterRegistryError):
    """Raised when a named adapter is not registered."""


class UnsupportedCapabilityError(AdapterRegistryError):
    """Raised when an adapter did not declare a requested capability."""


@dataclass(frozen=True)
class AdapterRegistration:
    name: str
    adapter: RoutingAdapter
    capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("adapter registration name must not be empty")
        if not self.capabilities:
            raise ValueError("adapter capabilities must not be empty")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("adapter capabilities must be unique")
        if not isinstance(self.adapter, RoutingAdapter):
            raise TypeError("adapter must satisfy the RoutingAdapter protocol")


class AdapterRegistry:
    """Small explicit registry for routing adapters."""

    def __init__(self, registrations: Sequence[AdapterRegistration] = ()) -> None:
        self._registrations: dict[str, AdapterRegistration] = {}
        for registration in registrations:
            self.register(
                registration.adapter,
                registration.capabilities,
                name=registration.name,
            )

    def register(
        self,
        adapter: RoutingAdapter,
        capabilities: Sequence[str],
        *,
        name: Optional[str] = None,
    ) -> AdapterRegistration:
        registration_name = name or adapter.adapter_name
        if registration_name in self._registrations:
            raise DuplicateAdapterError(
                f"adapter {registration_name!r} is already registered"
            )
        registration = AdapterRegistration(
            name=registration_name,
            adapter=adapter,
            capabilities=tuple(capabilities),
        )
        self._registrations[registration_name] = registration
        return registration

    def get(self, name: str) -> AdapterRegistration:
        try:
            return self._registrations[name]
        except KeyError as error:
            raise UnknownAdapterError(f"adapter {name!r} is not registered") from error

    def adapters_for(self, capability: str) -> tuple[AdapterRegistration, ...]:
        return tuple(
            registration
            for registration in self._registrations.values()
            if capability in registration.capabilities
        )

    def route(self, name: str, request: Mapping[str, object]) -> RouteDecision:
        registration = self.get(name)
        capability = request.get("capability")
        if capability not in registration.capabilities:
            raise UnsupportedCapabilityError(
                f"adapter {name!r} does not declare capability {capability!r}"
            )
        return registration.adapter.route(request)

    def snapshot(self) -> dict[str, tuple[str, ...]]:
        return {
            name: registration.capabilities
            for name, registration in sorted(self._registrations.items())
        }
