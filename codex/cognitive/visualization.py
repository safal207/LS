from __future__ import annotations

from typing import Dict, Iterable, Tuple


def render_bar(value: float, width: int = 20) -> str:
    clamped = min(1.0, max(0.0, value))
    filled = int(round(clamped * width))
    return f"[{'█' * filled}{'·' * (width - filled)}] {clamped:.2f}"


def render_attention(attention: Dict[str, float], limit: int = 5) -> str:
    if not attention:
        return ""
    ranked: Iterable[Tuple[str, float]] = sorted(attention.items(), key=lambda item: item[1], reverse=True)
    lines = [f"{thread}:{render_bar(score, width=12)}" for thread, score in list(ranked)[:limit]]
    return " | ".join(lines)
