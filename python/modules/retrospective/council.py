from __future__ import annotations

from datetime import datetime, timezone

from graph import CoalitionRegistry, DerivedModuleRegistry, RouteStatsStore

from .reports import RetrospectiveReport


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RetrospectiveCouncil:
    """Lightweight retrospective analysis over route, coalition, and derived-module memory."""

    def __init__(
        self,
        *,
        route_store: RouteStatsStore | None = None,
        coalition_registry: CoalitionRegistry | None = None,
        derived_module_registry: DerivedModuleRegistry | None = None,
    ) -> None:
        self.route_store = route_store or RouteStatsStore()
        self.coalition_registry = coalition_registry or CoalitionRegistry()
        self.derived_module_registry = derived_module_registry or DerivedModuleRegistry()

    def analyze(self) -> RetrospectiveReport:
        routes = self.route_store.list_routes()
        coalitions = self.coalition_registry.list_coalitions()
        modules = self.derived_module_registry.list_modules()

        strong_routes = [
            route.route_key
            for route in routes
            if route.runs >= 2 and route.avg_quality >= 0.7 and route.avg_goal_alignment >= 0.65 and route.pheromone_weight >= 0.25
        ]
        weak_routes = [
            route.route_key
            for route in routes
            if route.runs >= 2 and (route.avg_quality < 0.55 or route.avg_goal_alignment < 0.5 or route.pheromone_weight < 0.05)
        ]
        strong_coalitions = [
            coalition.route_key
            for coalition in coalitions
            if coalition.runs >= 1 and coalition.trust_score >= 0.7 and coalition.avg_quality >= 0.65
        ]
        weak_coalitions = [
            coalition.route_key
            for coalition in coalitions
            if coalition.runs >= 1 and (coalition.trust_score < 0.5 or coalition.avg_quality < 0.5)
        ]
        stale_modules = [
            module.module_id
            for module in modules
            if module.state in {"review", "retired"} or module.trust_score < 0.55 or module.quality_score < 0.6
        ]

        recommendations: list[str] = []
        if weak_routes:
            recommendations.append(f"reduce trust for weak routes: {', '.join(weak_routes[:3])}")
        if strong_routes:
            recommendations.append(f"prefer strong routes for similar tasks: {', '.join(strong_routes[:3])}")
        if strong_coalitions:
            recommendations.append(f"promote strong coalitions: {', '.join(strong_coalitions[:3])}")
        if weak_coalitions:
            recommendations.append(f"review weak coalitions: {', '.join(weak_coalitions[:3])}")
        if stale_modules:
            recommendations.append(f"run care cycles or retire stale modules: {', '.join(stale_modules[:3])}")
        if not recommendations:
            recommendations.append("network state is stable; continue collecting evidence")

        return RetrospectiveReport(
            timestamp=_utc_now(),
            strong_routes=strong_routes,
            weak_routes=weak_routes,
            strong_coalitions=strong_coalitions,
            weak_coalitions=weak_coalitions,
            stale_modules=stale_modules,
            recommendations=recommendations,
            summary={
                "route_count": len(routes),
                "coalition_count": len(coalitions),
                "derived_module_count": len(modules),
                "avg_route_goal_alignment": round(sum(route.avg_goal_alignment for route in routes) / len(routes), 4) if routes else 0.0,
            },
        )
