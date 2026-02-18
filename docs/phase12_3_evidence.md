# Evidence

## Before/After `agent.step()` orchestration

### Before
```python
def step(self):
    ...
    primary_intent=self.intentengine.select_primary_intent()
    self_snapshot = self.self_model.update_from_state(state)
    self.orientation.update_from_self_model(self.self_model)
    ...
```

### After
```python
def step(self):
    state = self.build_state()
    context = UpdateContext(..., primary_intent=None, ...)
    self_result = self.self_model.update(context)
    context = context.evolve(
        self_snapshot=self_result["snapshot"],
        meta_report=self_result.get("analysis"),
        metafeedback=self_result.get("metafeedback"),
    )
    orientation_result = self.orientation.update(context)
    context = context.evolve(orientation_snapshot=orientation_result["snapshot"])
    identity_result = self.identitycore.update(context)
    ...
    intent_result = self.intentengine.update(context)
    context = context.evolve(
        intent_snapshot=intent_result["snapshot"],
        primary_intent=intent_result["primary_intent"],
        intents=intent_result["intents"],
    )
```

## Removed legacy calls from `step()` path

- `intentengine.select_primary_intent()` removed from context initialization in `step()`.
- `self_model.update_from_state(...)` removed from `step()` orchestration.
- `orientation.update_from_self_model(...)` removed from `step()` orchestration.

## Test Results

```text
$ python -m pytest tests/test_context_propagation.py -q
..                                                                       [100%]
2 passed in 1.69s

$ python -m pytest python/tests/test_nca_culture_engine.py -q
..................                                                       [100%]
18 passed in 1.72s
```

## Semgrep Results

```text
GitHub Actions check: semgrep-scan
Status: completed
Conclusion: success
URL: https://github.com/safal207/LS/pull/131/checks
```

Notes:
- Local environment does not have `semgrep` installed, so enforcement evidence is sourced from CI.
- PR branch also includes policy files:
  - `.semgrep/phase12_1_regression_scan.yml`
  - `.semgrep/phase12_2_legacy_api_ban.yml`
  - `.semgrep/phase12_3_context_single_source.yml`

## Orchestration Layer Validation

`agent.step()` was scanned for forbidden legacy prefixes:

```text
step_range 121 239
matches 0
```

Blocked prefixes:
- `update_from_*`
- `generate_*`
- `select_*`
- `apply_*`
- `infer_*`
- `evaluate_*`

## Phase 13 completion note

`_update_self_layer()` compatibility helper has been removed.
Self-model and orientation updates now run directly in `step()` via `update(context)` and are propagated through `context.evolve(...)`.

## Why `primary_intent=None` is safe

- `UpdateContext.primary_intent` starts as `None` before the Intent Layer.
- The authoritative value is produced by `IntentEngine.update(context)`.
- `step()` writes it back via `context.evolve(...)` immediately after intent update.
- This prevents stale direct-selector usage and keeps deterministic layer ordering.

## Phase 13 Roadmap

1. Migrate self-model and orientation to context-native `update(context)` APIs.
2. Remove `_update_self_layer()` helper and compatibility tuple return pattern. ✅
3. Promote engine legacy-prefix warning rule (12.3) from `WARNING` to `ERROR`.
4. Remove legacy-prefixed helper methods after external API consumers are verified.
