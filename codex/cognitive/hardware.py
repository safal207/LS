from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


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
        topology = cls.get_cpu_topology()
        numa = cls.get_numa_topology()
        return {
            "cpu_percent": cls.get_cpu_usage(),
            "cpu_temp": cls.get_cpu_temp(),
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "swap_used_gb": cls.get_swap_usage(),
            "io_wait": cls.get_io_wait(),
            "topology": topology,
            "numa": numa,
        }

    @staticmethod
    def get_cpu_topology() -> Dict[str, Any]:
        psutil = _load_psutil()
        if psutil is None:
            return {}
        logical = psutil.cpu_count(logical=True)
        physical = psutil.cpu_count(logical=False)
        per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
        return {
            "logical_cpus": int(logical or 0),
            "physical_cores": int(physical or 0),
            "per_cpu_percent": [float(value) for value in per_cpu],
        }

    @staticmethod
    def get_numa_topology() -> Dict[str, Any]:
        node_root = Path("/sys/devices/system/node")
        if not node_root.exists():
            return {}
        nodes: Dict[str, Any] = {}
        for node_path in node_root.glob("node[0-9]*"):
            node_id = node_path.name.replace("node", "")
            cpulist_path = node_path / "cpulist"
            cpus = _parse_cpu_list(cpulist_path.read_text().strip()) if cpulist_path.exists() else []
            meminfo_path = node_path / "meminfo"
            mem_total_kb = None
            mem_free_kb = None
            if meminfo_path.exists():
                for line in meminfo_path.read_text().splitlines():
                    if "MemTotal" in line:
                        mem_total_kb = _parse_meminfo_kb(line)
                    if "MemFree" in line:
                        mem_free_kb = _parse_meminfo_kb(line)
            nodes[node_id] = {
                "cpus": cpus,
                "mem_total_gb": _kb_to_gb(mem_total_kb),
                "mem_free_gb": _kb_to_gb(mem_free_kb),
            }
        return {"nodes": nodes}


def _parse_cpu_list(cpulist: str) -> List[int]:
    cpus: List[int] = []
    for part in cpulist.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", maxsplit=1)
            cpus.extend(range(int(start), int(end) + 1))
        else:
            cpus.append(int(part))
    return cpus


def _parse_meminfo_kb(line: str) -> int | None:
    for token in line.split():
        if token.isdigit():
            return int(token)
    return None


def _kb_to_gb(value_kb: int | None) -> float | None:
    if value_kb is None:
        return None
    return round(value_kb / (1024**2), 3)
