from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from graph import CoalitionRegistry, DerivedModuleRegistry, RouteStatsStore

from .models import NetworkSnapshot


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrajectoryStore:
    def __init__(
        self,
        path: str | Path = "data/graph_memory/trajectory_snapshots.json",
        *,
        route_store: RouteStatsStore | None = None,
        coalition_registry: CoalitionRegistry | None = None,
        derived_module_registry: DerivedModuleRegistry | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.route_store = route_store or RouteStatsStore()
        self.coalition_registry = coalition_registry or CoalitionRegistry()
        self.derived_module_registry = derived_module_registry or DerivedModuleRegistry()

    def list_snapshots(self) -> list[NetworkSnapshot]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [NetworkSnapshot(**item) for item in raw if isinstance(item, dict)]

    def save_snapshot(self, snapshot: NetworkSnapshot) -> NetworkSnapshot:
        snapshots = self.list_snapshots()
        snapshots.append(snapshot)
        self.path.write_text(
            json.dumps([item.to_dict() for item in snapshots], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return snapshot

    def capture_snapshot(self) -> NetworkSnapshot:
        routes = self.route_store.list_routes()
        coalitions = self.coalition_registry.list_coalitions()
        modules = self.derived_module_registry.list_modules()

        route_health = {
            "count": len(routes),
            "strong": [
                route.route_key
                for route in routes
                if route.runs >= 2 and route.avg_quality >= 0.7 and route.pheromone_weight >= 0.2
            ],
            "weak": [
                route.route_key
                for route in routes
                if route.runs >= 2 and (route.avg_quality < 0.55 or route.pheromone_weight < 0.05)
            ],
            "avg_quality": round(sum(route.avg_quality for route in routes) / len(routes), 4) if routes else 0.0,
            "avg_latency_ms": round(sum(route.avg_latency_ms for route in routes) / len(routes), 2) if routes else 0.0,
        }
        coalition_health = {
            "count": len(coalitions),
            "strong": [
                coalition.route_key
                for coalition in coalitions
                if coalition.trust_score >= 0.7 and coalition.avg_quality >= 0.65
            ],
            "weak": [
                coalition.route_key
                for coalition in coalitions
                if coalition.runs >= 1 and (coalition.trust_score < 0.5 or coalition.avg_quality < 0.5)
            ],
            "avg_trust": round(sum(coalition.trust_score for coalition in coalitions) / len(coalitions), 4) if coalitions else 0.0,
        }
        derived_module_health = {
            "count": len(modules),
            "active": [module.module_id for module in modules if module.state == "active"],
            "review": [module.module_id for module in modules if module.state == "review"],
            "retired": [module.module_id for module in modules if module.state == "retired"],
            "avg_trust": round(sum(module.trust_score for module in modules) / len(modules), 4) if modules else 0.0,
            "avg_quality": round(sum(module.quality_score for module in modules) / len(modules), 4) if modules else 0.0,
        }

        adequacy_score = round(
            (
                route_health["avg_quality"] * 0.4
                + coalition_health["avg_trust"] * 0.3
                + derived_module_health["avg_quality"] * 0.3
            ),
            4,
        )
        avg_latency_ms = float(route_health["avg_latency_ms"] or 0.0)
        latency_score = round(max(0.0, 1.0 - min(1.0, avg_latency_ms / 30000.0)), 4)
        review_count = len(derived_module_health["review"])
        retired_count = len(derived_module_health["retired"])
        module_count = max(1, len(modules))
        drift_score = round(min(1.0, (review_count + retired_count) / module_count), 4)

        snapshot = NetworkSnapshot(
            snapshot_id=f"snapshot-{uuid.uuid4().hex[:8]}",
            timestamp=_utc_now(),
            route_health=route_health,
            coalition_health=coalition_health,
            derived_module_health=derived_module_health,
            adequacy_score=adequacy_score,
            latency_score=latency_score,
            drift_score=drift_score,
        )
        return self.save_snapshot(snapshot)
