# Rhythm Engine (Phase 13)

## Purpose

The Rhythm Engine provides a three-phase breathing signal:

- **inhale**: chaos expansion
- **hold**: integration pause
- **exhale**: harmony compression

It is a non-invasive regulator and does not change behavior.

## Inputs

The engine evaluates the following signals:

- diversity_score (Metabolic Diversity)
- stability_score (Belief Aging)
- contradiction_rate (Temporal Causality)
- drift_pressure (Cognitive Immunity)
- confidence_budget (Conviction Regulator)

## Phase Decision

```
chaos = diversity_score + contradiction_rate + drift_pressure
harmony = stability_score + confidence_budget

if abs(chaos - harmony) <= hold_epsilon -> hold
if chaos > harmony -> inhale
if harmony > chaos -> exhale
```

## Outputs

```
{
  "rhythm_phase": "inhale" | "hold" | "exhale",
  "chaos_score": float,
  "harmony_score": float,
  "delta": float
}
```

## Non-Goals

- No reasoning
- No behavior changes
- No persistence

## Tests

`tests/unit/test_rhythm_engine.py`
