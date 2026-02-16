# Phase 12.2 Reference Patch (Minimum)

This patch provides a concrete Phase 12.2 baseline with:
- a cleaner `agent.step()` orchestration path (no direct `values.evaluate_value_alignment(...)` call),
- one reference engine migrated around `update(context)`: `ValueSystem`.

## Updated Files
- `python/modules/nca/agent.py`
- `python/modules/nca/value_system.py`

## Agent Step Reference
- `agent.step()` now sources `value_alignment` from `values.update(context)`.
- `agent.step()` no longer calls `self.values.evaluate_value_alignment(...)` directly.
- `_finalize_step(...)` no longer triggers `self.values.evolve_preferences()` directly.

## ValueSystem Reference
`ValueSystem.update(context)` now performs:
1. context-driven sync from identity/collective/intents/autonomy
2. action derivation from context (`initiative`/`primary_intent`)
3. value alignment evaluation
4. preference evolution
5. returns `{snapshot, value_alignment}`

Legacy public APIs are retained as compatibility wrappers, but `update(context)` is the reference integration surface.

