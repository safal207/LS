# Attention Model (Phase 9)

## Mission
Provide a minimal, observable attention layer that can adapt focus based on
phase metrics and presence state without changing runtime behavior.

## Scope (v0.1)
- AttentionState: current focus, confidence, last_updated, history
- AttentionEngine: stub update(presence, metrics) -> AttentionState
- No behavior changes to AgentLoop or LLM

## Inputs
- PresenceState (goal, phase, focus, intent, context)
- Phase-aware metrics (durations, transitions, liminal frequency)

## Outputs
- AttentionState snapshot for observability and future integration

## Non-goals
- No policy enforcement
- No prompt rewriting
- No ranking or external retrieval
