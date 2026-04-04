from __future__ import annotations

from typing import Tuple

import psutil

from config import LLM_HEAVY_MODEL, LLM_LIGHT_MODEL, LLM_RAM_THRESHOLD_GB


def get_available_ram_gb() -> float:
    """Return currently available RAM in GB (cross-platform)."""
    return psutil.virtual_memory().available / (1024 ** 3)


def select_model(available_ram_gb: float | None = None) -> Tuple[str, str]:
    """Return (primary_model, fallback_model) based on available RAM."""
    available = available_ram_gb if available_ram_gb is not None else get_available_ram_gb()

    if available >= LLM_RAM_THRESHOLD_GB:
        return LLM_HEAVY_MODEL, LLM_LIGHT_MODEL
    return LLM_LIGHT_MODEL, LLM_LIGHT_MODEL
