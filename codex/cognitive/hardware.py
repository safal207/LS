from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Dict


def _load_psutil():
    spec = importlib.util.find_spec("psutil")
    if spec is None:
        return None
    return importlib.import_module("psutil")


@dataclass(frozen=True)
class HardwareMonitor:
    @staticmethod
    def get_cpu_usage() -> float | None:
        psutil = _load_psutil()
        if psutil is None:
            return None
        return float(psutil.cpu_percent(interval=0.1))

    @staticmethod
    def get_cpu_temp() -> float | None:
        psutil = _load_psutil()
        if psutil is None or not hasattr(psutil, "sensors_temperatures"):
            return None
        temps = psutil.sensors_temperatures(fahrenheit=False) or {}
        for readings in temps.values():
            if readings:
                return float(readings[0].current)
        return None

    @staticmethod
    def get_ram_usage() -> tuple[float | None, float | None]:
        psutil = _load_psutil()
        if psutil is None:
            return (None, None)
        vm = psutil.virtual_memory()
        return (float(vm.used) / (1024**3), float(vm.total) / (1024**3))

    @staticmethod
    def get_swap_usage() -> float | None:
        psutil = _load_psutil()
        if psutil is None:
            return None
        swap = psutil.swap_memory()
        return float(swap.used) / (1024**3)

    @staticmethod
    def get_io_wait() -> float | None:
        psutil = _load_psutil()
        if psutil is None or not hasattr(psutil, "cpu_times_percent"):
            return None
        times = psutil.cpu_times_percent(interval=0.1)
        return float(getattr(times, "iowait", 0.0))

    @classmethod
    def collect(cls) -> Dict[str, Any]:
        ram_used_gb, ram_total_gb = cls.get_ram_usage()
        return {
            "cpu_percent": cls.get_cpu_usage(),
            "cpu_temp": cls.get_cpu_temp(),
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "swap_used_gb": cls.get_swap_usage(),
            "io_wait": cls.get_io_wait(),
        }
