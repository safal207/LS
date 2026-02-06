# Field Resonance (Phase 17.1)

## Purpose

Compute coherence metrics across LS nodes in the shared Field Layer.
This phase computes metrics only; it does not influence LS decisions.

## Metrics (Skeleton)

- `orientation_coherence` — similarity of orientation vectors across nodes
- `confidence_alignment` — alignment of smoothed confidence across nodes
- `trajectory_tension` — divergence of trajectory_error across nodes

All metrics are floats in [0, 1] and return 0.0 for empty fields.

## Behavior

- Pure computation
- No feedback or bias
- No network communication

## Future

- Phase 17.2: Field-Aware Bias
