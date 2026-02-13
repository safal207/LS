from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Generic

from .transport import MessageT, TransportBackend


FactoryT = Callable[[], TransportBackend[MessageT]]


@dataclass
class TransportRegistry(Generic[MessageT]):
    _factories: Dict[str, FactoryT[MessageT]] = field(default_factory=dict)

    def register(self, transport_type: str, factory: FactoryT[MessageT]) -> None:
        self._factories[transport_type] = factory

    def create(self, transport_type: str) -> TransportBackend[MessageT]:
        if transport_type not in self._factories:
            raise KeyError(f"Unknown transport: {transport_type}")
        return self._factories[transport_type]()

    def available(self) -> list[str]:
        return sorted(self._factories.keys())
