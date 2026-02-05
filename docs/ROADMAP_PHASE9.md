# Phase 9 Roadmap: Cognitive Attention Model

## Goal
Introduce a minimal attention layer that can evolve into dynamic focus
allocation based on cognitive phase telemetry.

## Deliverables
### v0.1 (skeleton)
- AttentionState structure
- AttentionEngine stub
- Documentation (this roadmap + ATTENTION_MODEL)

### v0.2 (integration)
- Update Presence.focus + Presence.intent from AttentionEngine
- Emit attention_shift observability event
- Metrics-based focus decay and reinforcement

### v0.3 (analysis)
- Focus history windowing
- Confidence recalibration
- Attention heuristics using phase durations

## Integration Points
- PresenceState updates
- Observability event stream
- Phase metrics (durations, transitions)

## Tests
- AttentionState snapshot consistency
- AttentionEngine update contract (no side-effects)
