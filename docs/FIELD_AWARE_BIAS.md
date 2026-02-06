# Field-Aware Bias (Phase 17.2)

## Purpose
Provide a small, safe bias signal derived from Field Resonance metrics.
The bias is used as a *hint* for adaptive parameters, not for mode selection.

## Inputs
- `orientation_coherence`
- `confidence_alignment`
- `trajectory_tension`

## Outputs
```
{
  "orientation_bias": float,
  "confidence_bias": float,
  "trajectory_bias": float
}
```

All values are clamped to a small range ([-0.2, 0.2]).

## Behavior
- No mode switching
- No policy changes
- No persistence
- Best-effort only

## Safety
Coordinator applies Meta-Hygiene to clamp and stabilize all updates.

## Non-Goals
- No network communication
- No feedback loops
- No learning or optimization
