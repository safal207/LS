from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from .thread import CognitiveThread
from .workspace import GlobalFrame


@dataclass
class ThreadScheduler:
    threads: Dict[str, CognitiveThread] = field(default_factory=dict)

    def register_thread(self, thread: CognitiveThread) -> None:
        self.threads[thread.thread_id] = thread

    def sync_threads(self, threads: Iterable[CognitiveThread]) -> None:
        for thread in threads:
            self.register_thread(thread)

    def pause_thread(self, thread_id: str) -> None:
        thread = self.threads.get(thread_id)
        if thread:
            thread.active = False

    def resume_thread(self, thread_id: str) -> None:
        thread = self.threads.get(thread_id)
        if thread:
            thread.active = True

    def update_attention(self, frame: GlobalFrame) -> Dict[str, float]:
        thread = self.threads.get(frame.thread_id)
        if thread:
            thread.touch(frame.timestamp)
            if frame.merit_scores:
                avg_merit = sum(frame.merit_scores.values()) / len(frame.merit_scores)
                thread.attention_weight = max(0.1, (thread.attention_weight + avg_merit) / 2)
        self._apply_hardware_pressure(frame.hardware or {})
        self._apply_kernel_signals(frame.hardware.get("kernel") if isinstance(frame.hardware, dict) else {})
        self._apply_thread_placement(
            frame.hardware.get("topology") if isinstance(frame.hardware, dict) else {},
            frame.hardware.get("numa") if isinstance(frame.hardware, dict) else {},
        )
        self._apply_cpu_topology(frame.hardware.get("topology") if isinstance(frame.hardware, dict) else {})
        self._apply_numa_balance(frame.hardware.get("numa") if isinstance(frame.hardware, dict) else {})
        self._apply_thermal_policy(frame.hardware or {})
        self._apply_lri(frame.hardware.get("lri") if isinstance(frame.hardware, dict) else {})
        return self._normalize_attention(self._attention_scores())

    def select_active_thread(self) -> str | None:
        active_threads = [thread for thread in self.threads.values() if thread.active]
        if not active_threads:
            return None
        scored = sorted(
            active_threads,
            key=lambda thread: (
                self._attention_score(thread),
                thread.last_active_timestamp,
            ),
            reverse=True,
        )
        return scored[0].thread_id

    def _attention_scores(self, threads: Iterable[CognitiveThread] | None = None) -> Dict[str, float]:
        threads = list(threads or self.threads.values())
        return {thread.thread_id: self._attention_score(thread) for thread in threads}

    def _attention_score(self, thread: CognitiveThread) -> float:
        base = max(0.0, thread.priority) * max(0.0, thread.attention_weight)
        decay = self._attention_decay(thread.last_active_timestamp)
        return base * decay

    def _apply_hardware_pressure(self, hardware: Dict[str, Any]) -> None:
        if not self._is_overloaded(hardware):
            return
        for thread in self.threads.values():
            if thread.priority <= 0.3:
                thread.active = False
                continue
            if thread.priority >= 1.0:
                thread.attention_weight = max(0.1, thread.attention_weight * 0.8)
            else:
                thread.attention_weight = min(2.0, thread.attention_weight * 1.1)

    def _apply_kernel_signals(self, kernel: Dict[str, Any]) -> None:
        if not isinstance(kernel, dict):
            return
        signals = kernel.get("signals") or []
        if not isinstance(signals, list) or not signals:
            return
        for thread in self.threads.values():
            if "cache_thrashing" in signals:
                thread.attention_weight = max(0.1, thread.attention_weight * 0.85)
                if thread.priority <= 0.4:
                    thread.active = False
            if "iowait_spike" in signals:
                if getattr(thread, "tags", []) and "io-heavy" in getattr(thread, "tags", []):
                    thread.active = False
                elif thread.priority <= 0.5:
                    thread.attention_weight = max(0.1, thread.attention_weight * 0.8)
            if "branch_mispredict_storm" in signals:
                thread.attention_weight = max(0.1, thread.attention_weight * 0.9)
            if "context_switch_storm" in signals:
                if thread.priority >= 0.8:
                    thread.attention_weight = min(2.0, thread.attention_weight + 0.5)
                elif thread.priority <= 0.5:
                    thread.attention_weight = max(0.1, thread.attention_weight * 0.85)

    def _apply_cpu_topology(self, topology: Dict[str, Any]) -> None:
        if not isinstance(topology, dict):
            return
        per_cpu = topology.get("per_cpu_percent")
        if not isinstance(per_cpu, list) or not per_cpu:
            return
        for thread in self.threads.values():
            affinity = getattr(thread, "cpu_affinity", [])
            if not affinity:
                continue
            samples = [per_cpu[cpu] for cpu in affinity if isinstance(cpu, int) and cpu < len(per_cpu)]
            if not samples:
                continue
            avg_load = sum(samples) / len(samples)
            if avg_load >= 85:
                thread.attention_weight = max(0.1, thread.attention_weight * 0.85)
            elif avg_load <= 30:
                thread.attention_weight = min(2.0, thread.attention_weight * 1.05)

    def _apply_thread_placement(self, topology: Dict[str, Any], numa: Dict[str, Any]) -> None:
        if not isinstance(topology, dict):
            return
        per_cpu = topology.get("per_cpu_percent")
        if not isinstance(per_cpu, list) or not per_cpu:
            return
        nodes = numa.get("nodes") if isinstance(numa, dict) else None
        for thread in self.threads.values():
            if not getattr(thread, "cpu_affinity", None):
                if isinstance(nodes, dict) and nodes and getattr(thread, "numa_node", None) is not None:
                    node = nodes.get(str(thread.numa_node)) or nodes.get(thread.numa_node)
                    if isinstance(node, dict):
                        cpus = node.get("cpus")
                        if isinstance(cpus, list) and cpus:
                            thread.cpu_affinity = [self._least_loaded_cpu(per_cpu, cpus)]
                            continue
                if isinstance(nodes, dict) and nodes and getattr(thread, "numa_node", None) is None:
                    best_node = self._best_numa_node(nodes)
                    if best_node is not None:
                        thread.numa_node = best_node
                        cpus = nodes.get(str(best_node), {}).get("cpus") or nodes.get(best_node, {}).get("cpus")
                        if isinstance(cpus, list) and cpus:
                            thread.cpu_affinity = [self._least_loaded_cpu(per_cpu, cpus)]
                            continue
                thread.cpu_affinity = [self._least_loaded_cpu(per_cpu, list(range(len(per_cpu))))]

    def _apply_thermal_policy(self, hardware: Dict[str, Any]) -> None:
        cpu_temp = hardware.get("cpu_temp")
        if not isinstance(cpu_temp, (int, float)):
            return
        if cpu_temp >= 90:
            for thread in self.threads.values():
                if thread.priority <= 0.4:
                    thread.active = False
                thread.attention_weight = max(0.1, thread.attention_weight * 0.8)
        elif cpu_temp >= 80:
            for thread in self.threads.values():
                thread.attention_weight = max(0.1, thread.attention_weight * 0.9)

    def _apply_lri(self, lri: Dict[str, Any]) -> None:
        if not isinstance(lri, dict):
            return
        value = lri.get("value")
        if not isinstance(value, (int, float)):
            return
        for thread in self.threads.values():
            if value >= 0.8:
                if thread.priority < 0.7:
                    thread.active = False
                thread.attention_weight = max(0.1, thread.attention_weight * 0.8)
            elif value >= 0.5:
                if thread.priority < 0.4:
                    thread.attention_weight = max(0.1, thread.attention_weight * 0.9)
            else:
                if thread.priority >= 0.9:
                    thread.attention_weight = min(2.0, thread.attention_weight * 1.05)

    @staticmethod
    def _least_loaded_cpu(per_cpu: list[float], candidates: list[int]) -> int:
        best_cpu = candidates[0]
        best_load = per_cpu[best_cpu] if best_cpu < len(per_cpu) else 100.0
        for cpu in candidates:
            if cpu >= len(per_cpu):
                continue
            load = per_cpu[cpu]
            if load < best_load:
                best_load = load
                best_cpu = cpu
        return best_cpu

    @staticmethod
    def _best_numa_node(nodes: Dict[str, Any]) -> int | None:
        best_node = None
        best_ratio = -1.0
        for node_id, node in nodes.items():
            if not isinstance(node, dict):
                continue
            mem_free = node.get("mem_free_gb")
            mem_total = node.get("mem_total_gb")
            if isinstance(mem_free, (int, float)) and isinstance(mem_total, (int, float)) and mem_total:
                ratio = mem_free / mem_total
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_node = int(node_id)
        return best_node

    def _apply_numa_balance(self, numa: Dict[str, Any]) -> None:
        if not isinstance(numa, dict):
            return
        nodes = numa.get("nodes")
        if not isinstance(nodes, dict) or not nodes:
            return
        for thread in self.threads.values():
            node_id = getattr(thread, "numa_node", None)
            if node_id is None:
                continue
            node = nodes.get(str(node_id)) or nodes.get(node_id)
            if not isinstance(node, dict):
                continue
            mem_free = node.get("mem_free_gb")
            mem_total = node.get("mem_total_gb")
            if isinstance(mem_free, (int, float)) and isinstance(mem_total, (int, float)) and mem_total:
                free_ratio = mem_free / mem_total
                if free_ratio < 0.15:
                    thread.attention_weight = max(0.1, thread.attention_weight * 0.8)
    @staticmethod
    def _is_overloaded(hardware: Dict[str, Any]) -> bool:
        cpu_percent = hardware.get("cpu_percent")
        cpu_temp = hardware.get("cpu_temp")
        io_wait = hardware.get("io_wait")
        swap_used_gb = hardware.get("swap_used_gb")
        ram_used_gb = hardware.get("ram_used_gb")
        ram_total_gb = hardware.get("ram_total_gb")
        ram_percent = None
        if (
            isinstance(ram_used_gb, (int, float))
            and isinstance(ram_total_gb, (int, float))
            and ram_total_gb
        ):
            ram_percent = (ram_used_gb / ram_total_gb) * 100
        return any(
            [
                isinstance(cpu_percent, (int, float)) and cpu_percent > 80,
                isinstance(cpu_temp, (int, float)) and cpu_temp > 75,
                isinstance(io_wait, (int, float)) and io_wait > 5,
                isinstance(swap_used_gb, (int, float)) and swap_used_gb > 0,
                isinstance(ram_percent, (int, float)) and ram_percent > 80,
            ]
        )

    @staticmethod
    def _attention_decay(timestamp: str) -> float:
        try:
            last_active = datetime.fromisoformat(timestamp)
        except ValueError:
            last_active = datetime.now(timezone.utc)
        now = datetime.now(timezone.utc)
        delta = max(0.0, (now - last_active).total_seconds())
        return max(0.1, 1.0 - (delta / 300.0))

    @staticmethod
    def _normalize_attention(scores: Dict[str, float]) -> Dict[str, float]:
        total = sum(scores.values())
        if total <= 0:
            return {key: 0.0 for key in scores}
        return {key: value / total for key, value in scores.items()}
