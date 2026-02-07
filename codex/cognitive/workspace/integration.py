from __future__ import annotations

from .broadcaster import GlobalBroadcaster
from .bus import WorkspaceBus


def build_workspace() -> tuple[WorkspaceBus, GlobalBroadcaster]:
    bus = WorkspaceBus()
    broadcaster = GlobalBroadcaster(bus)
    return bus, broadcaster
