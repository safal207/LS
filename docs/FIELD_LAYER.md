# Field Layer (Phase 17.0)

## Purpose

Provide a minimal shared field that aggregates state snapshots from multiple LS
nodes. This phase is infrastructure only: no resonance, no bias influence.

## Inputs / Outputs

- Input: LS snapshot from Coordinator (orientation, confidence, trajectory)
- Output: aggregated `FieldState` containing per-node `FieldNodeState`

## Behavior (Skeleton)

- Local in-memory registry
- TTL-based cleanup for stale nodes
- No network transport
- No decision influence

## Non-Goals

- No resonance or feedback
- No biasing of Coordinator decisions
- No distributed sync
- No persistence

## Future Phases

- Phase 17.1: Resonance (field coherence)
- Phase 17.2: Field-aware bias
