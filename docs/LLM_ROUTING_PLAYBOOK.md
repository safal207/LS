# LLM Routing Playbook (Intent + Health + Fallback)

This project now supports a practical routing policy inspired by modern AI gateways:

- Intent-aware backend ranking (`realtime`, `batch`, `streaming`).
- Policy presets (`balanced`, `latency_optimized`, `cost_optimized`).
- Health-aware fallback ordering via per-backend telemetry.
- Built-in circuit breaker demotion (consecutive failures + cooldown).
- A/B mode for policy experiments and shadow mode for safe route evaluation.
- Explainability in response payload under `raw.route.explain`.

## 1) Request metadata contract

Pass routing metadata to the router:

```python
metadata = {
  "intent": "realtime",  # optional; inferred from user message if omitted
  "policy": "latency_optimized",  # balanced | latency_optimized | cost_optimized
  "backend_health": {
    "cloud": {"latency_ms": 400, "error_rate": 0.02, "load": 0.55, "cost": 0.8},
    "local": {"latency_ms": 130, "error_rate": 0.01, "load": 0.20, "cost": 0.1},
  },
  "health_thresholds": {
    "error_rate": 0.10,
    "latency_ms": 8000,
  },
  "breaker_failure_threshold": 3,
  "breaker_cooldown_seconds": 30,
  "pin_primary": False,  # set True to keep configured primary always first
  "routing_mode": "primary",  # primary | ab | shadow
  "ab_variant_ratio": 0.20,
  "ab_variant_policy": "cost_optimized",
  "shadow_policy": "cost_optimized",
  "request_id": "trace-123",  # deterministic bucketing for A/B
}
```

Missing fields are treated safely with defaults.

## 2) How route selection works

The router computes score for each backend in the base route:

```text
score = intent_fit - penalty
penalty = w_latency*latency_norm + w_error*error_norm + w_load*load_norm + w_cost*cost_norm
```

- `intent_fit`: backend suitability for the current intent.
- `penalty`: health and efficiency penalty according to selected policy.
- unhealthy backends are demoted when they exceed thresholds.
- breaker-open backends are demoted until cooldown expires.
- primary can be pinned with `pin_primary=True` when deterministic order is required.

## 3) Explainability payload

Every call includes explain data:

```python
response.raw["route"]["explain"]
```

Shape:

- `intent`, `policy`
- `base_route` and `effective`
- `scores[]` (per backend: `intent_fit`, `penalty`, `score`, `unhealthy`, stats)
- `health_thresholds`
- `breaker` config + per-backend circuit telemetry in each score row

Use this for dashboards and incident triage.

## 4) Recommended rollout

1. Start with `balanced` and record explain payloads.
2. Enable intent tagging from API layer.
3. Feed real backend telemetry (`latency_ms`, `error_rate`, `load`, `cost`).
4. Switch selected traffic segments to `latency_optimized` or `cost_optimized`.
5. Keep fallback chain with at least one local provider for resilience.

## 5) A/B and shadow runbook

- `routing_mode=ab`:
  - set `ab_variant_ratio` from `0.05` to `0.20` during rollout;
  - keep stable bucketing via `request_id` or `trace_id`;
  - compare `p95`, `error_rate`, and unit cost between baseline and variant.
- `routing_mode=shadow`:
  - production response uses primary route only;
  - shadow route is computed and written to `explain.shadow`;
  - use shadow comparisons before raising A/B traffic.

## 6) Runtime control plane usage

- Use `set_runtime_overrides(policy=..., health_thresholds=...)` to hot-adjust routing without code edits.
- Use `clear_runtime_overrides()` to return to request-driven/default behavior.
- Persist override changes via your admin API layer, then emit an audit event.

## 7) Observability fields

`response.raw["route"]["stats"]` now includes counters:

- `requests_total`
- `fallback_total`
- `ab_variant_selected_total`
- `shadow_evaluations_total`
- `backend_success_total` / `backend_failure_total`

Export these counters to Prometheus or your telemetry sink.

## 8) Minimal test checklist

- Fallback triggers when primary fails.
- Intent can reorder fallback candidates.
- Unhealthy backend is demoted in effective route.
- Circuit breaker opens after N consecutive failures and demotes that backend.
- A/B mode chooses variant policy when bucket is selected.
- Shadow mode emits `explain.shadow` without changing primary execution safety.
- Explain payload is present in `raw.route.explain`.
