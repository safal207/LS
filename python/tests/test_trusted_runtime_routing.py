from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.adapters.dao_lim import DAOlimConfig, DAOlimRoutingAdapter
from modules.trusted_runtime.registry import (
    AdapterRegistry,
    DuplicateAdapterError,
    UnsupportedCapabilityError,
)
from modules.trusted_runtime.routing import (
    BackendCandidate,
    DeterministicRoutingAdapter,
    MalformedRouteResponseError,
    NoRouteError,
    RoutingDisabledError,
    RoutingTimeoutError,
    route_decision_event,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/routing"
SCHEMA = ROOT / "schemas/trusted_runtime/route_decision.schema.json"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _request() -> dict:
    return {
        "task_id": "task-routing-001",
        "trail_id": "trail-routing-001",
        "role_id": "verifier",
        "capability": "evidence_verification",
        "actor": "runtime:ls",
        "created_at": "2026-06-23T10:00:00Z",
        "parent_cause": "event-plan-created",
        "constraints": {
            "max_latency_ms": 500,
            "min_reliability": 0.95,
            "required_privacy": "private",
            "max_cost_per_1k": 1.0,
            "max_load": 0.8,
        },
    }


def _candidate(payload: dict) -> BackendCandidate:
    return BackendCandidate(
        backend_id=payload["backend_id"],
        capabilities=tuple(payload["capabilities"]),
        latency_ms=payload["latency_ms"],
        reliability=payload["reliability"],
        load=payload.get("load", 0.0),
        privacy=payload.get("privacy", "standard"),
        cost_per_1k=payload.get("cost_per_1k", 0.0),
        approved=payload.get("approved", True),
        available=payload.get("available", True),
        degraded=payload.get("degraded", False),
        fallback=payload.get("fallback", False),
    )


def _schema_errors(payload: dict) -> list:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return list(Draft202012Validator(schema).iter_errors(payload))


def test_registry_declares_capabilities_and_rejects_duplicates() -> None:
    fixture = _load("deterministic_route.json")
    adapter = DeterministicRoutingAdapter(
        [_candidate(item) for item in fixture["candidates"]]
    )
    registry = AdapterRegistry()
    registration = registry.register(adapter, ["evidence_verification"])

    assert registration.name == "deterministic-mock"
    assert registry.snapshot() == {
        "deterministic-mock": ("evidence_verification",)
    }
    decision = registry.route("deterministic-mock", _request())
    assert decision.selected_backend == "local-verifier"

    with pytest.raises(DuplicateAdapterError):
        registry.register(adapter, ["evidence_verification"])
    with pytest.raises(UnsupportedCapabilityError):
        registry.route(
            "deterministic-mock",
            {**_request(), "capability": "implementation"},
        )


def test_deterministic_router_selects_explainable_schema_valid_route() -> None:
    fixture = _load("deterministic_route.json")
    adapter = DeterministicRoutingAdapter(
        [_candidate(item) for item in fixture["candidates"]]
    )

    first = adapter.route(_request())
    second = adapter.route(_request())

    assert first.to_dict() == second.to_dict()
    assert first.selected_backend == fixture["expected"]["selected_backend"]
    assert first.considered_backends == tuple(
        fixture["expected"]["considered_backends"]
    )
    assert first.metadata["scores"][first.selected_backend]["total"] >= 0
    assert first.metadata["rejected_backends"]["public-fast"] == [
        "privacy_below_requirement"
    ]
    assert first.metadata["rejected_backends"]["unapproved-cheap"] == [
        "not_approved"
    ]
    assert _schema_errors(first.to_dict()) == []


def test_fallback_is_explicit_and_never_uses_unapproved_backend() -> None:
    fixture = _load("fallback_route.json")
    adapter = DeterministicRoutingAdapter(
        [_candidate(item) for item in fixture["candidates"]]
    )
    decision = adapter.route({**_request(), "constraints": fixture["constraints"]})

    assert decision.selected_backend == "private-fallback"
    assert decision.metadata["fallback_used"] is True
    assert "fallback tier used" in decision.reason
    assert "unapproved-fallback" in decision.metadata["rejected_backends"]


def test_no_route_fails_closed() -> None:
    fixture = _load("no_route.json")
    adapter = DeterministicRoutingAdapter(
        [_candidate(item) for item in fixture["candidates"]]
    )
    with pytest.raises(NoRouteError, match="no approved backend"):
        adapter.route({**_request(), "constraints": fixture["constraints"]})


def test_dao_lim_is_disabled_by_default() -> None:
    adapter = DAOlimRoutingAdapter()
    with pytest.raises(RoutingDisabledError):
        adapter.route(_request())


def test_dao_lim_sends_only_route_metadata_and_preserves_safe_explainability() -> None:
    captured = {}

    def transport(payload, config):
        captured.update(payload)
        return {
            "selected_backend": "dao-private",
            "considered_backends": ["dao-private", "dao-secondary"],
            "reason": "lowest resonant score under private policy",
            "scores": {
                "dao-private": 0.12,
                "dao-secondary": 0.21,
            },
            "metrics": {"p95_ms": 42, "error_rate": 0.001},
            "explainability": {
                "load_resonance": 0.1,
                "intent_gap": 0.0,
                "api_token": "must-not-survive",
            },
        }

    adapter = DAOlimRoutingAdapter(
        DAOlimConfig(enabled=True, mode="http"),
        transport=transport,
    )
    request = {
        **_request(),
        "intent": "private task content must not leave LS",
        "provider_secret": "must-not-leave",
        "routing_intent": "evidence-verification",
        "approved_backends": ["dao-private", "dao-secondary"],
    }
    decision = adapter.route(request)
    event = route_decision_event(decision)

    assert "intent" not in captured
    assert "provider_secret" not in captured
    assert captured["capability"] == "evidence_verification"
    assert decision.selected_backend == "dao-private"
    assert "api_token" not in decision.metadata["dao_explain"]
    assert event.payload["explainability"]["metrics"]["p95_ms"] == 42
    assert event.payload["considered_backends"] == [
        "dao-private",
        "dao-secondary",
    ]
    assert _schema_errors(decision.to_dict()) == []


@pytest.mark.parametrize(
    ("fixture_name", "error_type"),
    [
        ("dao_timeout.json", RoutingTimeoutError),
        ("dao_malformed.json", MalformedRouteResponseError),
        ("dao_no_route.json", NoRouteError),
    ],
)
def test_dao_lim_negative_fixtures(
    fixture_name: str,
    error_type: type[Exception],
) -> None:
    fixture = _load(fixture_name)

    def transport(payload, config):
        if fixture["behavior"] == "timeout":
            raise TimeoutError
        return fixture["response"]

    adapter = DAOlimRoutingAdapter(
        DAOlimConfig(enabled=True),
        transport=transport,
    )
    with pytest.raises(error_type):
        adapter.route(_request())
