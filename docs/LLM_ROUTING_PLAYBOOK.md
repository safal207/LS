# LLM Routing Playbook (Intent + Health + Fallback)

This project now supports a practical routing policy inspired by modern AI gateways:

- Intent-aware backend ranking (`realtime`, `batch`, `streaming`).
- Policy presets (`balanced`, `latency_optimized`, `cost_optimized`).
- Health-aware fallback ordering via per-backend telemetry.
- Explainability in response payload under `raw.route.explain`.

## 1) Request metadata contract

Pass routing metadata to the router:

```python
metadata = {
  "intent": "realtime",  # realtime | batch | streaming
  "policy": "latency_optimized",  # balanced | latency_optimized | cost_optimized
  "backend_health": {
    "cloud": {"latency_ms": 400, "error_rate": 0.02, "load": 0.55, "cost": 0.8},
    "local": {"latency_ms": 130, "error_rate": 0.01, "load": 0.20, "cost": 0.1},
  },
  "health_thresholds": {
    "error_rate": 0.10,
    "latency_ms": 8000,
  },
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
- primary backend remains first in route order for deterministic behavior.

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

Use this for dashboards and incident triage.

## 4) Recommended rollout

1. Start with `balanced` and record explain payloads.
2. Enable intent tagging from API layer.
3. Feed real backend telemetry (`latency_ms`, `error_rate`, `load`, `cost`).
4. Switch selected traffic segments to `latency_optimized` or `cost_optimized`.
5. Keep fallback chain with at least one local provider for resilience.

## 5) Minimal test checklist

- Fallback triggers when primary fails.
- Intent can reorder fallback candidates.
- Unhealthy backend is demoted in effective route.
- Explain payload is present in `raw.route.explain`.

