from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from .contracts import RouteDecision, TrailEvent, TrailEventType


JsonObject = Mapping[str, Any]

PRIVACY_LEVELS: Mapping[str, int] = {
    "public": 0,
    "standard": 1,
    "private": 2,
    "local": 3,
}


class RoutingError(RuntimeError):
    """Base class for fail-closed routing errors."""


class NoRouteError(RoutingError):
    """Raised when no approved backend satisfies the declared policy."""


class RoutingDisabledError(RoutingError):
    """Raised when an optional routing integration is not enabled."""


class RoutingTimeoutError(RoutingError):
    """Raised when a routing transport exceeds its timeout."""


class MalformedRouteResponseError(RoutingError):
    """Raised when an external router returns an unusable response."""


class RoutingUnavailableError(RoutingError):
    """Raised when a routing transport is unavailable."""


@dataclass(frozen=True)
class BackendCandidate:
    backend_id: str
    capabilities: tuple[str, ...]
    latency_ms: float
    reliability: float
    load: float = 0.0
    privacy: str = "standard"
    cost_per_1k: float = 0.0
    approved: bool = True
    available: bool = True
    degraded: bool = False
    fallback: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("backend_id must not be empty")
        if not self.capabilities:
            raise ValueError("backend capabilities must not be empty")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("backend capabilities must be unique")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be between 0 and 1")
        if not 0.0 <= self.load <= 1.0:
            raise ValueError("load must be between 0 and 1")
        if self.privacy not in PRIVACY_LEVELS:
            raise ValueError(f"unsupported privacy level: {self.privacy}")
        if self.cost_per_1k < 0:
            raise ValueError("cost_per_1k must be non-negative")


@dataclass(frozen=True)
class RoutingPolicy:
    max_latency_ms: Optional[float] = None
    min_reliability: float = 0.0
    max_load: float = 1.0
    required_privacy: str = "public"
    max_cost_per_1k: Optional[float] = None
    allow_degraded: bool = False
    allow_fallback: bool = True
    approved_backends: tuple[str, ...] = ()
    latency_weight: float = 0.35
    reliability_weight: float = 0.30
    load_weight: float = 0.20
    cost_weight: float = 0.15

    def __post_init__(self) -> None:
        if self.max_latency_ms is not None and self.max_latency_ms <= 0:
            raise ValueError("max_latency_ms must be positive")
        if not 0.0 <= self.min_reliability <= 1.0:
            raise ValueError("min_reliability must be between 0 and 1")
        if not 0.0 <= self.max_load <= 1.0:
            raise ValueError("max_load must be between 0 and 1")
        if self.required_privacy not in PRIVACY_LEVELS:
            raise ValueError(f"unsupported privacy level: {self.required_privacy}")
        if self.max_cost_per_1k is not None and self.max_cost_per_1k < 0:
            raise ValueError("max_cost_per_1k must be non-negative")
        if len(self.approved_backends) != len(set(self.approved_backends)):
            raise ValueError("approved_backends must be unique")
        weights = (
            self.latency_weight,
            self.reliability_weight,
            self.load_weight,
            self.cost_weight,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("routing weights must be non-negative")
        if sum(weights) <= 0:
            raise ValueError("at least one routing weight must be positive")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RoutingPolicy":
        allowed = {
            "max_latency_ms",
            "min_reliability",
            "max_load",
            "required_privacy",
            "max_cost_per_1k",
            "allow_degraded",
            "allow_fallback",
            "approved_backends",
            "latency_weight",
            "reliability_weight",
            "load_weight",
            "cost_weight",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"unknown routing policy fields: {sorted(unknown)}")
        values = dict(payload)
        values["approved_backends"] = tuple(values.get("approved_backends", ()))
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_latency_ms": self.max_latency_ms,
            "min_reliability": self.min_reliability,
            "max_load": self.max_load,
            "required_privacy": self.required_privacy,
            "max_cost_per_1k": self.max_cost_per_1k,
            "allow_degraded": self.allow_degraded,
            "allow_fallback": self.allow_fallback,
            "approved_backends": list(self.approved_backends),
            "weights": {
                "latency": self.latency_weight,
                "reliability": self.reliability_weight,
                "load": self.load_weight,
                "cost": self.cost_weight,
            },
        }


@dataclass(frozen=True)
class _CandidateScore:
    backend_id: str
    total: float
    latency: float
    reliability: float
    load: float
    cost: float

    def to_dict(self) -> dict[str, float]:
        return {
            "total": self.total,
            "latency": self.latency,
            "reliability": self.reliability,
            "load": self.load,
            "cost": self.cost,
        }


class DeterministicRoutingAdapter:
    """Provider-neutral deterministic router for tests and local workflows."""

    def __init__(
        self,
        candidates: Sequence[BackendCandidate],
        adapter_name: str = "deterministic-mock",
    ) -> None:
        if not adapter_name:
            raise ValueError("adapter_name must not be empty")
        if not candidates:
            raise ValueError("at least one backend candidate is required")
        identifiers = [candidate.backend_id for candidate in candidates]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("backend identifiers must be unique")
        self._candidates = tuple(candidates)
        self._adapter_name = adapter_name

    @property
    def adapter_name(self) -> str:
        return self._adapter_name

    def route(self, request: JsonObject) -> RouteDecision:
        capability = _required_string(request, "capability")
        policy_payload = request.get("constraints", {})
        if not isinstance(policy_payload, Mapping):
            raise TypeError("routing constraints must be a mapping")
        policy = RoutingPolicy.from_mapping(policy_payload)

        primary, primary_rejected = self._eligible(
            capability,
            policy,
            fallback=False,
        )
        selected_pool = primary
        rejected = dict(primary_rejected)
        fallback_used = False

        if not selected_pool and policy.allow_fallback:
            fallback, fallback_rejected = self._eligible(
                capability,
                policy,
                fallback=True,
            )
            selected_pool = fallback
            rejected.update(fallback_rejected)
            fallback_used = bool(fallback)

        if not selected_pool:
            reasons = "; ".join(
                f"{backend}: {','.join(values)}"
                for backend, values in sorted(rejected.items())
            )
            suffix = f" ({reasons})" if reasons else ""
            raise NoRouteError(
                f"no approved backend satisfies capability {capability!r}{suffix}"
            )

        scores = tuple(self._score(candidate, policy) for candidate in selected_pool)
        ordered_scores = tuple(
            sorted(scores, key=lambda item: (item.total, item.backend_id))
        )
        selected = ordered_scores[0]
        considered = tuple(item.backend_id for item in ordered_scores)
        alternatives = considered[1:]
        reason = (
            f"selected {selected.backend_id} with deterministic score "
            f"{selected.total:.6f}"
        )
        if alternatives:
            reason += f"; alternatives: {', '.join(alternatives)}"
        if fallback_used:
            reason += "; fallback tier used"

        metadata = {
            "explainability_version": "trusted_runtime.routing.explain.v0.1",
            "fallback_used": fallback_used,
            "policy": policy.to_dict(),
            "scores": {item.backend_id: item.to_dict() for item in ordered_scores},
            "rejected_backends": rejected,
        }
        return RouteDecision(
            route_id=str(
                request.get(
                    "route_id",
                    "route-"
                    f"{_required_string(request, 'role_id')}-"
                    f"{selected.backend_id}",
                )
            ),
            task_id=_required_string(request, "task_id"),
            trail_id=_required_string(request, "trail_id"),
            role_id=_required_string(request, "role_id"),
            capability=capability,
            adapter=self.adapter_name,
            actor=str(request.get("actor", f"adapter:{self.adapter_name}")),
            selected_backend=selected.backend_id,
            considered_backends=considered,
            reason=reason,
            created_at=_required_string(request, "created_at"),
            parent_cause=_required_string(request, "parent_cause"),
            metadata=metadata,
        )

    def _eligible(
        self,
        capability: str,
        policy: RoutingPolicy,
        fallback: bool,
    ) -> tuple[tuple[BackendCandidate, ...], dict[str, list[str]]]:
        eligible = []
        rejected: dict[str, list[str]] = {}
        for candidate in self._candidates:
            if candidate.fallback is not fallback:
                continue
            reasons = self._rejection_reasons(candidate, capability, policy)
            if reasons:
                rejected[candidate.backend_id] = reasons
            else:
                eligible.append(candidate)
        return tuple(eligible), rejected

    @staticmethod
    def _rejection_reasons(
        candidate: BackendCandidate,
        capability: str,
        policy: RoutingPolicy,
    ) -> list[str]:
        reasons = []
        if capability not in candidate.capabilities:
            reasons.append("capability_mismatch")
        if not candidate.approved:
            reasons.append("not_approved")
        if (
            policy.approved_backends
            and candidate.backend_id not in policy.approved_backends
        ):
            reasons.append("not_in_allowlist")
        if not candidate.available:
            reasons.append("unavailable")
        if candidate.degraded and not policy.allow_degraded:
            reasons.append("degraded")
        if PRIVACY_LEVELS[candidate.privacy] < PRIVACY_LEVELS[policy.required_privacy]:
            reasons.append("privacy_below_requirement")
        if (
            policy.max_latency_ms is not None
            and candidate.latency_ms > policy.max_latency_ms
        ):
            reasons.append("latency_above_limit")
        if candidate.reliability < policy.min_reliability:
            reasons.append("reliability_below_limit")
        if candidate.load > policy.max_load:
            reasons.append("load_above_limit")
        if (
            policy.max_cost_per_1k is not None
            and candidate.cost_per_1k > policy.max_cost_per_1k
        ):
            reasons.append("cost_above_limit")
        return reasons

    @staticmethod
    def _score(candidate: BackendCandidate, policy: RoutingPolicy) -> _CandidateScore:
        latency_scale = policy.max_latency_ms or 1000.0
        latency = min(candidate.latency_ms / latency_scale, 10.0)
        reliability = 1.0 - candidate.reliability
        load = candidate.load
        if policy.max_cost_per_1k is not None and policy.max_cost_per_1k > 0:
            cost = min(candidate.cost_per_1k / policy.max_cost_per_1k, 10.0)
        else:
            cost = candidate.cost_per_1k
        total = (
            policy.latency_weight * latency
            + policy.reliability_weight * reliability
            + policy.load_weight * load
            + policy.cost_weight * cost
        )
        return _CandidateScore(
            backend_id=candidate.backend_id,
            total=round(total, 6),
            latency=round(latency, 6),
            reliability=round(reliability, 6),
            load=round(load, 6),
            cost=round(cost, 6),
        )


def route_decision_event(
    decision: RouteDecision,
    *,
    event_id: Optional[str] = None,
    parent_cause: Optional[str] = None,
) -> TrailEvent:
    """Convert a route decision into a safe explainability trail event."""

    return TrailEvent(
        event_id=event_id or f"event-{decision.route_id}",
        task_id=decision.task_id,
        trail_id=decision.trail_id,
        event_type=TrailEventType.ROUTE_SELECTED,
        actor=decision.actor,
        created_at=decision.created_at,
        parent_cause=parent_cause or decision.parent_cause,
        payload={
            "route_id": decision.route_id,
            "role_id": decision.role_id,
            "capability": decision.capability,
            "adapter": decision.adapter,
            "selected_backend": decision.selected_backend,
            "considered_backends": list(decision.considered_backends),
            "reason": decision.reason,
            "explainability": _sanitize(decision.metadata),
        },
    )


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            parts = set(normalized.split("_"))
            if parts & {
                "secret",
                "token",
                "password",
                "authorization",
                "credential",
                "apikey",
            }:
                continue
            if normalized in {"api_key", "access_key", "private_key"}:
                continue
            result[str(key)] = _sanitize(item)
        return result
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value
