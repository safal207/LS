# Phase 12.3 Hotspots (Current Branch Snapshot)

This note tracks remaining migration debt before strict Phase 13 enforcement.

## 1) `agent.step()` self-layer migration

- `agent.step()` no longer calls `self_model.update_from_*` or `orientation.update_from_*` directly.
- Legacy self/orientation update calls were moved to helper:
  - `python/modules/nca/agent.py` -> `_update_self_layer(...)`

### Self-Model / Orientation (Deferred to Phase 13)

- `self_model.update_from_state(state)`
- `orientation.update_from_self_model(self.self_model)`

Status:
- moved out of `agent.step()` into `_update_self_layer()` migration helper,
- not called directly in the step orchestration path,
- planned for clean `update(context)` migration in Phase 13.

## 2) `primary_intent` context semantics

- `UpdateContext.primary_intent` is initialized to `None`.
- Source of truth is `IntentEngine.update(context)` in Intent Layer.
- After Intent Layer, step updates:
  - `context.primary_intent`
  - `context.intent_snapshot`
  - `context.intents`

Safety note:
- `primary_intent` is not consumed as final intent before Intent Layer completion.
- This keeps pre-intent context deterministic without stale direct selector calls.

## 3) Engine `update(context)` methods still using legacy-prefixed helpers

- `python/modules/nca/identity_core.py:89`
- `python/modules/nca/social_cognition.py:35`
- `python/modules/nca/culture_engine.py:48`
- `python/modules/nca/militocracy_engine.py:27`
- `python/modules/nca/synergy_engine.py:27`
- `python/modules/nca/value_system.py:45`
- `python/modules/nca/autonomy_engine.py:34`
- `python/modules/nca/intent_engine.py:27`

Current status: acceptable as migration debt in 12.3 with warning-level policy.

## 4) Context initialization cleanup opportunities

- `UpdateContext` carries broad snapshot fields to support staged migration.
- Some fields may be pruned once all engines become fully context-native and stop reading backward-compat data.

## 5) Policy posture

- Phase 12.1 rules: blocker (stable gate)
- Phase 12.2 rules: strict migration guard
- Phase 12.3 rules: blocker on step-level legacy engine calls, warning on engine-update debt
