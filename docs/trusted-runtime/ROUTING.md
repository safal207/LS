# Trusted Runtime routing and DAO_lim adapter

Status: **reference implementation for issue #593**

LS decides which capability a workflow role needs. A routing adapter decides
which approved concrete backend may provide that capability under the current
latency, reliability, load, privacy, and cost policy.

```text
Workflow role
-> declared capability
-> adapter registry
-> routing policy
-> approved candidate set
-> explainable RouteDecision
-> ROUTE_SELECTED trail event
```

## Adapter registry

`AdapterRegistry` stores adapters by explicit name and explicit capability
list. Registration is intentionally small and local:

```python
registry = AdapterRegistry()
registry.register(
    deterministic_router,
    ["research", "evidence_verification"],
)
decision = registry.route("deterministic-mock", request)
```

Duplicate names and undeclared capabilities fail before the adapter is called.

## Deterministic local router

`DeterministicRoutingAdapter` is the dependency-free reference implementation.
It evaluates `BackendCandidate` records against `RoutingPolicy` constraints:

- required capability;
- backend approval and optional request allowlist;
- availability and degraded state;
- maximum latency and load;
- minimum reliability;
- required privacy level;
- maximum cost per 1,000 units.

Eligible candidates receive a deterministic weighted score. Lower is better.
Ties are resolved by backend identifier, so the same request and candidate set
produce the same route.

A fallback candidate is considered only when no primary candidate is eligible
and `allow_fallback` is true. Fallback never bypasses approval, privacy, cost,
reliability, latency, or load constraints.

When no route satisfies policy, the adapter raises `NoRouteError`. It does not
silently choose an unavailable, degraded, or unapproved backend.

## Explainability

Every `RouteDecision` includes:

- selected backend;
- ordered alternatives considered;
- human-readable reason;
- deterministic score components;
- rejected backends and rejection reasons;
- whether the fallback tier was used;
- the policy applied.

`route_decision_event()` converts this information into a `ROUTE_SELECTED`
Cognitive Trail event. Secret-like keys are removed recursively before metadata
is written to the trail.

## DAO_lim integration

`DAOlimRoutingAdapter` is optional and disabled by default. Core LS works
without DAO_lim installed.

```python
config = DAOlimConfig(
    enabled=True,
    mode="cli",  # or "http"
    timeout_seconds=2.0,
)
adapter = DAOlimRoutingAdapter(config)
```

CLI mode invokes the configurable equivalent of:

```text
daoctl explain --host <host> --path <path> --intent <routing-tag> --json
```

HTTP mode sends a JSON POST to the configured explain endpoint.

The adapter transmits only routing metadata:

- capability;
- role identifier;
- routing intent tag;
- sanitized constraints;
- configured host and path.

It does **not** transmit task content, user prompt text, provider credentials,
or API secrets. An explicit `approved_backends` allowlist is required before a
DAO_lim result can become an LS `RouteDecision`.

## Failure behavior

The integration fails closed:

| Condition | Result |
| --- | --- |
| feature flag disabled | `RoutingDisabledError` |
| timeout | `RoutingTimeoutError` |
| unavailable transport | `RoutingUnavailableError` |
| malformed JSON or missing fields | `MalformedRouteResponseError` |
| no route or unapproved selection | `NoRouteError` |

No failure path silently selects a provider.

## Secret handling

Do not put secrets in routing requests. Configuration contains endpoint and
command information only. Provider keys remain in the provider or DAO_lim
runtime environment and are never copied into `RouteDecision` or Cognitive
Trail artifacts.

## Validation

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_routing.py
```

Fixtures cover deterministic selection, fallback, no-route, DAO_lim timeout,
malformed response, and explicit no-route behavior under:

```text
python/tests/fixtures/trusted-runtime/routing/
```
