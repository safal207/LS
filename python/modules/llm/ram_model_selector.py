from __future__ import annotations

from typing import Tuple

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

from ..config import LLM_HEAVY_MODEL, LLM_LIGHT_MODEL, LLM_RAM_THRESHOLD_GB


def get_available_ram_gb() -> float:
    """Return currently available RAM in GB (cross-platform)."""
    if psutil is None:
        return 0.0
    return psutil.virtual_memory().available / (1024 ** 3)


def select_model(available_ram_gb: float | None = None) -> Tuple[str, str]:
    """Return (primary_model, fallback_model) based on available RAM."""
    available = available_ram_gb if available_ram_gb is not None else get_available_ram_gb()

    if available >= LLM_RAM_THRESHOLD_GB:
        return LLM_HEAVY_MODEL, LLM_LIGHT_MODEL
    return LLM_LIGHT_MODEL, LLM_LIGHT_MODEL
