from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RouteStats:
    route_key: str
    pheromone_weight: float = 0.0
    runs: int = 0
    successes: int = 0
    avg_quality: float = 0.0
    avg_latency_ms: float = 0.0
    last_used_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RouteStats":
        return cls(
            route_key=str(data.get("route_key", "")),
            pheromone_weight=float(data.get("pheromone_weight", 0.0) or 0.0),
            runs=int(data.get("runs", 0) or 0),
            successes=int(data.get("successes", 0) or 0),
            avg_quality=float(data.get("avg_quality", 0.0) or 0.0),
            avg_latency_ms=float(data.get("avg_latency_ms", 0.0) or 0.0),
            last_used_at=data.get("last_used_at"),
        )


class RouteStatsStore:
    def __init__(self, path: str | Path = "data/graph_memory/routes.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_routes(self) -> list[RouteStats]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [RouteStats.from_dict(item) for item in raw if isinstance(item, dict)]

    def get_route(self, route_key: str) -> Optional[RouteStats]:
        for route in self.list_routes():
            if route.route_key == route_key:
                return route
        return None

    def save_route(self, route: RouteStats) -> RouteStats:
        routes = self.list_routes()
        updated = False
        for idx, current in enumerate(routes):
            if current.route_key == route.route_key:
                routes[idx] = route
                updated = True
                break
        if not updated:
            routes.append(route)
        self._write(routes)
        return route

    def touch_route(self, route_key: str) -> RouteStats:
        route = self.get_route(route_key) or RouteStats(route_key=route_key)
        route.last_used_at = _utc_now()
        return self.save_route(route)

    def _write(self, routes: list[RouteStats]) -> None:
        payload = [route.to_dict() for route in routes]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
