from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Dict

from .engine import AdaptiveEngine
from .graph import CausalGraph
from .store import MemoryRecord, MemoryStore


class CausalMemoryLayer:
    def __init__(self, store_path: str | Path | None = None) -> None:
        self.store = MemoryStore(store_path or Path("causal_memory") / "memory.jsonl")
        self.graph = CausalGraph()
        self.engine = AdaptiveEngine(self.store, self.graph)

    def record_benchmark(
        self,
        *,
        model: str,
        model_type: str,
        metrics: Dict[str, Any],
        parameters: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord.build(
            model=model,
            model_type=model_type,
            inputs={"benchmark": model_type, "metadata": dict(metadata or {})},
            outputs={},
            parameters=dict(parameters or {}),
            hardware=self._collect_hardware_profile(),
            metrics=dict(metrics),
            success=success,
            error=error,
            tags=["benchmark"],
        )
        self.store.add(record)
        self.graph.observe(record)
        return record

    def record_task(
        self,
        *,
        model: str,
        model_type: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        parameters: Dict[str, Any] | None = None,
        hardware: Dict[str, Any] | None = None,
        metrics: Dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord.build(
            model=model,
            model_type=model_type,
            inputs=dict(inputs),
            outputs=dict(outputs),
            parameters=dict(parameters or {}),
            hardware=dict(hardware or {}),
            metrics=dict(metrics or {}),
            success=success,
            error=error,
            tags=list(tags or ["task"]),
        )
        self.store.add(record)
        self.graph.observe(record)
        return record

    @staticmethod
    def _collect_hardware_profile() -> Dict[str, Any]:
        profile: Dict[str, Any] = {"platform": platform.platform()}
        psutil = _load_psutil()
        if psutil is None:
            return profile

        profile["cpu_count"] = psutil.cpu_count(logical=True)
        memory = psutil.virtual_memory()
        profile["ram_gb"] = round(memory.total / (1024**3), 2)

        if psutil.cpu_freq() is not None:
            profile["cpu_mhz"] = round(psutil.cpu_freq().current, 2)

        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                profile["temps"] = {
                    name: [round(entry.current, 2) for entry in entries]
                    for name, entries in temps.items()
                }

        if _has_cuda():
            profile["vram_gb"] = _cuda_vram_gb()

        return profile


def _has_cuda() -> bool:
    import importlib.util

    if importlib.util.find_spec("torch") is None:
        return False
    import torch

    return torch.cuda.is_available()


def _cuda_vram_gb() -> float:
    import torch

    if not torch.cuda.is_available():
        return 0.0
    props = torch.cuda.get_device_properties(0)
    return round(props.total_memory / (1024**3), 2)


def _load_psutil():
    try:
        import psutil
        return psutil
    except ImportError:
        return None
