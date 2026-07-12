"""Deterministic contracts and simulation for multi-session coordination."""

from .contracts import (
    ContractViolation,
    canonical_sha256,
    classify_dependency_release,
    validate_coordination_event,
    validate_lifecycle_receipt,
    validate_route_result,
    validate_scenario,
)
from .simulator import (
    RouteProfile,
    RouteRun,
    apply_pareto_frontier,
    render_markdown_report,
    simulate_route,
)

__all__ = [
    "ContractViolation",
    "RouteProfile",
    "RouteRun",
    "apply_pareto_frontier",
    "canonical_sha256",
    "classify_dependency_release",
    "render_markdown_report",
    "simulate_route",
    "validate_coordination_event",
    "validate_lifecycle_receipt",
    "validate_route_result",
    "validate_scenario",
]
