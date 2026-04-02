from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .route_stats import RouteStats, RouteStatsStore


@dataclass
class PathExecutionRecord:
    route_key: str
    question_text: str
    graph_mode: str
    selected_backend: str
    quality: dict[str, Any]
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _quality_value(quality: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(quality.get(key, default) or default)
    except Exception:
        return default


def compute_route_reward(quality: dict[str, Any], latency_ms: float) -> float:
    overall = _quality_value(quality, "overall", _quality_value(quality, "resonance_score", 0.5))
    relevance = _quality_value(quality, "relevance", overall)
    thread_relevance = _quality_value(quality, "thread_relevance", overall)
    coherence = _quality_value(quality, "coherence", overall)
    goal_alignment = _quality_value(quality, "goal_alignment_score", overall)
    hallucination_risk = _quality_value(quality, "hallucination_risk", max(0.0, 1.0 - overall))
    latency_penalty = min(1.0, max(0.0, float(latency_ms) / 30000.0))
    reward = (
        0.28 * overall
        + 0.18 * relevance
        + 0.18 * thread_relevance
        + 0.12 * coherence
        + 0.14 * goal_alignment
        - 0.20 * hallucination_risk
        - 0.10 * latency_penalty
    )
    return round(reward, 4)


class TrailUpdater:
    def __init__(self, store: RouteStatsStore, *, decay: float = 0.95) -> None:
        self.store = store
        self.decay = decay

    def update(self, record: PathExecutionRecord) -> tuple[RouteStats, float]:
        route = self.store.get_route(record.route_key) or RouteStats(route_key=record.route_key)
        reward = compute_route_reward(record.quality, record.latency_ms)
        runs = route.runs
        route.pheromone_weight = round((route.pheromone_weight * self.decay) + reward, 4)
        route.runs = runs + 1
        route.successes += 1 if reward > 0 else 0
        overall = _quality_value(record.quality, "overall", _quality_value(record.quality, "resonance_score", 0.5))
        goal_alignment = _quality_value(record.quality, "goal_alignment_score", overall)
        route.avg_quality = round(((route.avg_quality * runs) + overall) / (runs + 1), 4)
        route.avg_goal_alignment = round(((route.avg_goal_alignment * runs) + goal_alignment) / (runs + 1), 4)
        route.avg_latency_ms = round(((route.avg_latency_ms * runs) + float(record.latency_ms)) / (runs + 1), 2)
        updated = self.store.touch_route(route.route_key)
        updated.pheromone_weight = route.pheromone_weight
        updated.runs = route.runs
        updated.successes = route.successes
        updated.avg_quality = route.avg_quality
        updated.avg_goal_alignment = route.avg_goal_alignment
        updated.avg_latency_ms = route.avg_latency_ms
        saved = self.store.save_route(updated)
        return saved, reward
