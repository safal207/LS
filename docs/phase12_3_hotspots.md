# Phase 12.3 Hotspots (Current Branch Snapshot)

This note tracks remaining migration debt before strict Phase 13 enforcement.

## 1) `agent.step()` legacy-adjacent calls

- `python/modules/nca/agent.py:124`
  - `self.self_model.update_from_state(state)`
- `python/modules/nca/agent.py:128`
  - `self.orientation.update_from_self_model(self.self_model)`

These are not engine cross-calls, but still use `update_from_*` naming and should be reviewed for final orchestration purity.

## 2) Engine `update(context)` methods still using legacy-prefixed helpers

- `python/modules/nca/identity_core.py:89`
- `python/modules/nca/social_cognition.py:35`
- `python/modules/nca/culture_engine.py:48`
- `python/modules/nca/militocracy_engine.py:27`
- `python/modules/nca/synergy_engine.py:27`
- `python/modules/nca/value_system.py:45`
- `python/modules/nca/autonomy_engine.py:34`
- `python/modules/nca/intent_engine.py:27`

Current status: acceptable as migration debt in 12.3 with warning-level policy.

## 3) Context initialization cleanup opportunities

- `UpdateContext` carries broad snapshot fields to support staged migration.
- Some fields may be pruned once all engines become fully context-native and stop reading backward-compat data.

## 4) Policy posture

- Phase 12.1 rules: blocker (stable gate)
- Phase 12.2 rules: strict migration guard
- Phase 12.3 rules: blocker on step-level legacy engine calls, warning on engine-update debt

