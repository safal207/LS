from __future__ import annotations

from dataclasses import dataclass, field

from .kernel_sensors import KernelSensorListener, KernelSensorMonitor


@dataclass
class KernelRuntime:
    listener: KernelSensorListener = field(default_factory=KernelSensorListener)
    running: bool = False

    def start(self) -> None:
        if self.running:
            return
        self.listener.start()
        KernelSensorMonitor.attach_listener(self.listener)
        self.running = True

    def stop(self) -> None:
        if not self.running:
            return
        self.listener.stop()
        self.running = False
