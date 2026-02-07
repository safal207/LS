from __future__ import annotations

import json
import math
import os
import socket
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class KernelTelemetry:
    timestamp: float
    syscalls: Dict[str, float]
    iowait_ms: float
    context_switches: float
    page_faults: float
    perf: Dict[str, float]
    hpi: float
    cli: float


class KernelSensorMonitor:
    _default_socket = "/tmp/kacl.sock"

    @classmethod
    def collect(cls) -> Dict[str, Any]:
        message = cls._read_message()
        if not message:
            return {"signals": [], "state": "stable", "telemetry": {}}
        signals = cls._signals_from_message(message)
        state = cls._state_from_message(message, signals)
        return {
            "signals": signals,
            "state": state,
            "telemetry": dict(message),
        }

    @classmethod
    def _read_message(cls) -> Dict[str, Any] | None:
        socket_path = os.getenv("KACL_SOCKET", cls._default_socket)
        if not os.path.exists(socket_path):
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.settimeout(0.01)
                sock.connect(socket_path)
                sock.send(b"poll")
                payload = sock.recv(65535)
        except (OSError, socket.timeout):
            return None
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    @classmethod
    def _signals_from_message(cls, message: Dict[str, Any]) -> List[str]:
        signals: List[str] = []
        telemetry = cls._parse_telemetry(message)
        if telemetry is None:
            return signals
        if telemetry.hpi >= 0.75 or telemetry.cli >= 0.75:
            signals.append("kernel_overload")
        if telemetry.iowait_ms >= 25.0:
            signals.append("iowait_spike")
        if telemetry.perf.get("cache_misses", 0.0) >= 250_000:
            signals.append("cache_thrashing")
        if telemetry.perf.get("branch_mispredicts", 0.0) >= 50_000:
            signals.append("branch_mispredict_storm")
        if telemetry.context_switches >= 2_000:
            signals.append("context_switch_storm")
        if telemetry.syscalls and sum(telemetry.syscalls.values()) >= 10_000:
            signals.append("syscall_flood")
        cpu_temp = message.get("cpu_temp")
        if isinstance(cpu_temp, (int, float)) and cpu_temp >= 85:
            signals.append("thermal_throttling")
        return signals

    @classmethod
    def _state_from_message(cls, message: Dict[str, Any], signals: Iterable[str]) -> str:
        if "kernel_overload" in signals:
            return "overload"
        telemetry = cls._parse_telemetry(message)
        if telemetry is None:
            return "stable"
        if telemetry.hpi <= 0.3 and telemetry.cli <= 0.3:
            return "high_throughput"
        return "stable"

    @classmethod
    def _parse_telemetry(cls, message: Dict[str, Any]) -> KernelTelemetry | None:
        try:
            perf = message.get("perf") or {}
            syscalls = message.get("syscalls") or {}
            return KernelTelemetry(
                timestamp=float(message.get("timestamp", 0.0)),
                syscalls={k: float(v) for k, v in syscalls.items()},
                iowait_ms=float(message.get("iowait_ms", 0.0)),
                context_switches=float(message.get("context_switches", 0.0)),
                page_faults=float(message.get("page_faults", 0.0)),
                perf={k: float(v) for k, v in perf.items()},
                hpi=float(message.get("hpi", 0.0)),
                cli=float(message.get("cli", 0.0)),
            )
        except (TypeError, ValueError):
            return None


def syscall_entropy(syscalls: Dict[str, float]) -> float:
    total = sum(syscalls.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in syscalls.values():
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log(p, 2)
    max_entropy = math.log(len(syscalls), 2) if len(syscalls) > 1 else 1.0
    return min(1.0, entropy / max_entropy) if max_entropy else 0.0
