from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Optional

from .coalition_registry import CoalitionRegistry
from .route_stats import RouteStats, RouteStatsStore


@dataclass
class PathSelectionDecision:
    route_key: str
    reason: str
    exploration_used: bool = False
    pheromone_weight: float = 0.0
    selected_backend: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class PathSelector:
    def __init__(
        self,
        store: RouteStatsStore,
        *,
        coalition_registry: CoalitionRegistry | None = None,
        exploration_rate: float = 0.10,
        rng: random.Random | None = None,
    ) -> None:
        self.store = store
        self.coalition_registry = coalition_registry
        self.exploration_rate = max(0.0, min(1.0, exploration_rate))
        self.rng = rng or random.Random()

    def choose_route(
        self,
        *,
        graph_mode: str,
        available_backends: list[str],
        default_backend: str | None = None,
        intent: str | None = None,
        why_tag: str | None = None,
    ) -> PathSelectionDecision:
        if graph_mode == "reuse":
            route = self.store.touch_route("reuse")
            return PathSelectionDecision(
                route_key="reuse",
                reason="reuse-path",
                exploration_used=False,
                pheromone_weight=route.pheromone_weight,
                selected_backend=None,
            )

        candidates: list[tuple[str, str, RouteStats]] = []
        backend_set = set(available_backends)
        for backend in available_backends:
            route_key = f"{graph_mode}>{backend}"
            stats = self.store.get_route(route_key) or RouteStats(route_key=route_key)
            candidates.append((route_key, backend, stats))
        if {"local", "gonka", "mimo"}.issubset(backend_set):
            cooperative_route = f"{graph_mode}>local>gonka>mimo"
            cooperative_stats = self.store.get_route(cooperative_route) or RouteStats(route_key=cooperative_route)
            candidates.append((cooperative_route, "cooperative", cooperative_stats))

        if not candidates:
            route_key = graph_mode or "full_run"
            route = self.store.touch_route(route_key)
            return PathSelectionDecision(
                route_key=route_key,
                reason="no-backend-candidates",
                pheromone_weight=route.pheromone_weight,
            )

        coalition = None
        if self.coalition_registry is not None:
            coalition = self.coalition_registry.select_best(
                available_backends=available_backends,
                intent=intent,
                why_tag=why_tag,
            )
        if coalition is not None:
            stats = self.store.get_route(coalition.route_key) or RouteStats(route_key=coalition.route_key)
            self.store.touch_route(coalition.route_key)
            return PathSelectionDecision(
                route_key=coalition.route_key,
                reason="coalition-registry",
                exploration_used=False,
                pheromone_weight=max(stats.pheromone_weight, coalition.trust_score),
                selected_backend="cooperative" if len(coalition.members) > 1 else (coalition.members[0] if coalition.members else None),
            )

        use_exploration = len(candidates) > 1 and self.rng.random() < self.exploration_rate
        cooperative_candidate = next((item for item in candidates if item[1] == "cooperative"), None)
        if cooperative_candidate is not None:
            cooperative_zero_history = cooperative_candidate[2].runs == 0
            all_zero_history = all(item[2].runs == 0 for item in candidates)
            if cooperative_zero_history and all_zero_history and not use_exploration:
                route_key, backend, stats = cooperative_candidate
                self.store.touch_route(route_key)
                return PathSelectionDecision(
                    route_key=route_key,
                    reason="default-cooperative",
                    exploration_used=False,
                    pheromone_weight=stats.pheromone_weight,
                    selected_backend=backend,
                )

        if use_exploration:
            route_key, backend, stats = self.rng.choice(candidates)
            reason = "exploration"
        else:
            candidates.sort(key=lambda item: (item[2].pheromone_weight, item[2].avg_quality), reverse=True)
            route_key, backend, stats = candidates[0]
            if stats.runs == 0 and backend == "cooperative":
                reason = "default-cooperative"
            elif stats.runs == 0 and default_backend:
                route_key = f"{graph_mode}>{default_backend}"
                backend = default_backend
                stats = self.store.get_route(route_key) or RouteStats(route_key=route_key)
                reason = "default-backend"
            else:
                reason = "best-pheromone"

        self.store.touch_route(route_key)
        return PathSelectionDecision(
            route_key=route_key,
            reason=reason,
            exploration_used=use_exploration,
            pheromone_weight=stats.pheromone_weight,
            selected_backend=backend,
        )
