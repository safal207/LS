# Orientation Fusion Layer (Phase 13.3)

## Purpose

The Fusion Layer combines raw organ signals into a unified, smoothed
OrientationSignals vector. It does not change behavior.

## Inputs

- diversity_score
- stability_score
- contradiction_rate
- drift_pressure
- confidence_budget

## Smoothing

Skeleton smoothing uses EMA-style blending:

```
smoothed = alpha * prev + (1 - alpha) * current
```

First call returns raw signals. Subsequent calls blend with previous state.

## Outputs

- OrientationSignals (smoothed)

## Non-Goals

- No policy logic
- No persistence beyond in-memory prev state
- No side effects
