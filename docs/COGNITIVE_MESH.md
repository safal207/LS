Cognitive Mesh (Phase 22)

Purpose
Extract and reinforce stable distributed patterns from field metrics to form
a self-organizing cognitive fabric.

Behavior
- Slow EMA-like reinforcement.
- Mesh state remains in [0.0, 1.0].
- No direct influence on mode selection.
- No cross-node synchronization.

Safety
- Clamped values.
- No feedback loops.
- No persistence outside FieldRegistry.

Non-Goals
- No learning.
- No optimization.
- No consensus.
