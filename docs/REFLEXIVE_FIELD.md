# Reflexive Cognitive Field (Phase 26)

## Purpose
Provide a meta-stability layer that observes metric changes over time and applies gentle, bounded corrections to avoid overly sharp swings or excessive inertia.

## Behavior
- Computes a simple trend (first derivative) per metric: `trend = current - previous`.
- Produces a soft adjustment per metric: `adjustment = -lr * trend`.
- Clamps each adjustment to the safety range `[-0.1, 0.1]`.
- Applies the adjustment after topology updates and re-clamps the final metrics to `[0.0, 1.0]`.

## Safety
- No new metrics are created.
- Adjustments are bounded and applied additively.
- The final metric values remain in `[0.0, 1.0]`.

## Non-Goals
- Not a self-awareness or introspection module.
- Does not alter topology, morphogenesis, or resonance logic.
- Does not create feedback loops or change mode selection.

## Examples
- If `trajectory_tension` rises from `0.2` to `0.8` with `lr=0.05`:
  - `trend = 0.6`
  - `adjustment = -0.03`
  - new value becomes `0.77` (clamped if needed).
- If a metric is unchanged, the trend is `0` and the adjustment is `0`.
