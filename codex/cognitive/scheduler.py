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
        self._apply_cpu_topology(frame.hardware.get("topology") if isinstance(frame.hardware, dict) else {})
        self._apply_numa_balance(frame.hardware.get("numa") if isinstance(frame.hardware, dict) else {})
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
