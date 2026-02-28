"""Causal Memory Layer for Codex."""

from __future__ import annotations

import os
import time
from typing import Any, Callable


def with_file_lock(file_path: str, callback: Callable[[], Any], timeout: float = 10.0) -> Any:
    """Cross-platform exclusive lock using a sidecar .lock file."""
    lock_path = file_path + ".lock"
    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    deadline = time.monotonic() + timeout
    fd: int | None = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except OSError:
            if time.monotonic() > deadline:
                try:
                    os.unlink(lock_path)
                except OSError:
                    pass
            time.sleep(0.05)

    try:
        return callback()
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(lock_path)
        except OSError:
            pass

from .engine import AdaptiveEngine
from .graph import CausalEdge, CausalGraph
from .layer import CausalMemoryLayer
from .store import MemoryRecord, MemoryStore
from .amygdala import Amygdala, AmygdalaBlockError, BlockReason
from .memory import MemoryService
from .transitions import CausalMemoryTransitions, CausalNode
<<<<<<< HEAD
from .memory_service import MemoryService
=======
>>>>>>> main

__all__ = [
    "AdaptiveEngine",
    "CausalEdge",
    "CausalGraph",
    "CausalMemoryLayer",
    "MemoryRecord",
    "MemoryStore",
    "Amygdala",
    "AmygdalaBlockError",
    "BlockReason",
    "CausalMemoryTransitions",
    "CausalNode",
    "MemoryService",
<<<<<<< HEAD
=======
    "with_file_lock",
>>>>>>> main
]
