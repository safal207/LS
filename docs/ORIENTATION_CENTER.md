# Orientation Center (Phase 13)

## Overview

The Orientation Center (O) is a lightweight, non-invasive layer that provides
orientation signals to the rest of the system. It does not change behavior.

Phase 13.2 added modular organs. Phase 13.3 adds the Fusion Layer to combine
organ signals into a unified state vector before rhythm evaluation.

## Modules

- Metabolic Diversity -> diversity_score
- Belief Aging -> stability_score
- Temporal Causality -> contradiction_rate
- Cognitive Immunity -> drift_pressure
- Conviction Regulator -> confidence_budget
- Fusion Layer -> smoothed OrientationSignals
- Rhythm Engine -> inhale/hold/exhale
- Trajectory Adapter -> trajectory_signal (Phase 14.2)

## Outputs

```
{
  "rhythm_phase": "inhale" | "hold" | "exhale",
  "chaos_score": float,
  "harmony_score": float,
  "delta": float,
  "diversity_score": float,
  "stability_score": float,
  "contradiction_rate": float,
  "drift_pressure": float,
  "confidence_budget": float,
  "trajectory_signal": float
}
```

## Trajectory Signal (Phase 14.2)

Orientation Center accepts `trajectory_error` from the Trajectory Layer and
normalizes it into `trajectory_signal`. The signal is included in the output
but does not affect rhythm or behavior.

## Non-Goals

- No policy enforcement
- No mode switching
- No behavior modification
- No persistence
