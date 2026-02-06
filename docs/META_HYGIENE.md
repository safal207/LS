# Meta-Hygiene (Phase 16.1)

## Purpose

Stabilize Meta-Adaptation by preventing runaway parameter tuning and keeping
adaptive parameters within safe bounds.

## Inputs

- `trajectory_error`
- `confidence_smoothed`
- Current adaptation parameters:
  - `ConfidenceDynamics.alpha`
  - `ConfidenceDynamics.max_delta`

## Outputs

- Corrected parameters (clamped / reset to baseline when needed)

## Behavior (Skeleton)

- Detects spikes in `alpha` and `max_delta`
- Clamps parameters to safe bounds
- Resets to baseline after repeated spikes
- Does **not** change decision modes

## Non-Goals

- No policy learning
- No persistence
- No behavior changes outside parameter bounds
