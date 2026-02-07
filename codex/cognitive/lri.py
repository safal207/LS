from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class LRIResult:
    value: float
    state: str
    tags: List[str]


class LRILayer:
    @classmethod
    def compute(cls, hardware: Dict[str, Any] | None, kernel: Dict[str, Any] | None) -> LRIResult:
        hardware = hardware or {}
        kernel = kernel or {}

        components: List[float] = []
        tags: List[str] = []

        cpu_percent = hardware.get("cpu_percent")
        if isinstance(cpu_percent, (int, float)):
            components.append(min(1.0, cpu_percent / 100.0))
            if cpu_percent > 80:
                tags.append("cpu_bound")

        ram_used = hardware.get("ram_used_gb")
        ram_total = hardware.get("ram_total_gb")
        if isinstance(ram_used, (int, float)) and isinstance(ram_total, (int, float)) and ram_total:
            ram_pct = (ram_used / ram_total) * 100
            components.append(min(1.0, ram_pct / 100.0))
            if ram_pct > 80:
                tags.append("memory_pressure")

        io_wait = hardware.get("io_wait")
        if isinstance(io_wait, (int, float)):
            components.append(min(1.0, io_wait / 20.0))
            if io_wait > 5:
                tags.append("io_bound")

        cpu_temp = hardware.get("cpu_temp")
        if isinstance(cpu_temp, (int, float)):
            components.append(min(1.0, max(0.0, (cpu_temp - 40.0) / 50.0)))
            if cpu_temp > 80:
                tags.append("thermal_risk")

        telemetry = kernel.get("telemetry") if isinstance(kernel.get("telemetry"), dict) else {}
        hpi = telemetry.get("hpi")
        cli = telemetry.get("cli")
        if isinstance(hpi, (int, float)):
            components.append(max(0.0, min(1.0, hpi)))
        if isinstance(cli, (int, float)):
            components.append(max(0.0, min(1.0, cli)))

        signals = kernel.get("signals") or []
        if "kernel_overload" in signals:
            components.append(1.0)
            tags.append("kernel_overload")
        if "cache_thrashing" in signals:
            tags.append("cache_thrashing")
        if "context_switch_storm" in signals:
            tags.append("context_switch_storm")
        if "iowait_spike" in signals:
            tags.append("iowait_spike")

        numa = hardware.get("numa", {})
        nodes = numa.get("nodes") if isinstance(numa.get("nodes"), dict) else {}
        for node in nodes.values():
            if not isinstance(node, dict):
                continue
            mem_free = node.get("mem_free_gb")
            mem_total = node.get("mem_total_gb")
            if isinstance(mem_free, (int, float)) and isinstance(mem_total, (int, float)) and mem_total:
                if mem_free / mem_total < 0.15:
                    components.append(0.8)
                    tags.append("numa_pressure")
                    break

        topology = hardware.get("topology", {})
        per_cpu = topology.get("per_cpu_percent")
        if isinstance(per_cpu, list):
            max_cpu = max((v for v in per_cpu if isinstance(v, (int, float))), default=None)
            if isinstance(max_cpu, (int, float)) and max_cpu > 85:
                components.append(0.9)
                tags.append("cpu_hotspot")

        value = sum(components) / len(components) if components else 0.0
        if value >= 0.8:
            state = "overload"
        elif value >= 0.5:
            state = "elevated"
        else:
            state = "stable"

        return LRIResult(value=value, state=state, tags=sorted(set(tags)))
