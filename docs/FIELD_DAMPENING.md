# Field Dampening (Phase 18.1)

## Purpose
Stabilize Field Resonance metrics by applying smoothing and dampening to
reduce oscillations and distributed drift.

## Inputs
Raw field metrics from FieldResonance:
- `orientation_coherence`
- `confidence_alignment`
- `trajectory_tension`

## Outputs
Smoothed metrics with the same keys, values in [0.0, 1.0].

## Behavior
- Exponential moving average (EMA) per metric key.
- Stateful per FieldRegistry instance.
- No mode switching.
- No policy changes.

## Safety
- All outputs are clamped to [0.0, 1.0].
- If no metrics are available, returns an empty dict.

## Non-Goals
- No network communication.
- No learning or optimization.
- No direct feedback into LS decisions.
