# Self-Evolving Field Dynamics (Phase 21)

## Purpose
Allow the field to adapt its own internal weights based on long-term trends
in coherence, alignment, and tension.

## Behavior
- Slow EMA-like evolution.
- Weights remain in [0.5, 2.0].
- No direct influence on mode selection.
- No cross-node synchronization.

## Safety
- Clamped weights.
- No feedback loops.
- No persistence outside FieldRegistry.

## Non-Goals
- No learning.
- No optimization.
- No global coordination.
