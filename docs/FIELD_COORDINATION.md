# Field-Driven Coordination (Phase 19)

## Purpose
Provide a small, safe coordination bias derived from field metrics to gently
influence mode selection without overriding local autonomy.

## Behavior
- Computes a bias in [-0.2, 0.2].
- Positive bias nudges toward Mode B (deep).
- Negative bias nudges toward Mode A (fast).
- Never overrides ModeDetector.
- Applied only as a confidence adjustment.

## Safety
- Clamped values.
- No direct mode switching.
- No feedback loops.
- No persistence.

## Non-Goals
- No distributed consensus.
- No global decision-making.
- No cross-node synchronization.
