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
    context, self_snapshot, analysis, metafeedback = self._update_self_layer(state, context)
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
- `self_model.update_from_state(...)` moved into `_update_self_layer(...)`.
- `orientation.update_from_self_model(...)` moved into `_update_self_layer(...)`.

## Tests

```bash
python -m pytest tests/test_context_propagation.py -q
python -m pytest python/tests/test_nca_culture_engine.py -q
```

## Semgrep policy commands

```bash
semgrep --config .semgrep/phase12_1_regression_scan.yml --error
semgrep --config .semgrep/phase12_2_legacy_api_ban.yml --error
semgrep --config .semgrep/phase12_3_context_single_source.yml --error
```

