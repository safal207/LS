from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable

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
        self._apply_hardware_pressure(frame.hardware)
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

    def _apply_hardware_pressure(self, hardware: Dict[str, object]) -> None:
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

    @staticmethod
    def _is_overloaded(hardware: Dict[str, object]) -> bool:
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
