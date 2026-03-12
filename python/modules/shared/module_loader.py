from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol

from modules.shared.bootstrap import RuntimeContext


@dataclass(frozen=True)
class ModuleLifecycleEvent:
    type: str
    payload: dict


class RuntimeModule(Protocol):
    name: str

    def setup(self, ctx: RuntimeContext) -> None:
        ...

    def shutdown(self, ctx: RuntimeContext) -> None:
        ...


@dataclass
class _LoadedModule:
    module: RuntimeModule


class DynamicModuleLoader:
    """Registers runtime modules and wires them to context services."""

    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self._modules: Dict[str, _LoadedModule] = {}

    def load(self, module: RuntimeModule) -> None:
        if module.name in self._modules:
            raise KeyError(f"Module already loaded: {module.name}")
        module.setup(self.ctx)
        self._modules[module.name] = _LoadedModule(module=module)
        self.ctx.event_bus.publish(ModuleLifecycleEvent("module_loaded", {"name": module.name}))

    def unload(self, module_name: str) -> None:
        if module_name not in self._modules:
            return
        loaded = self._modules.pop(module_name)
        loaded.module.shutdown(self.ctx)
        self.ctx.event_bus.publish(ModuleLifecycleEvent("module_unloaded", {"name": module_name}))

    def list_loaded(self) -> list[str]:
        return sorted(self._modules.keys())
