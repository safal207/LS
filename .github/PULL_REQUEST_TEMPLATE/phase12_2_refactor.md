## Phase 12.2 PR Checklist

### Summary
Describe exactly which engines were migrated and what legacy calls were removed.

### Scope
- [ ] `agent.step()` orchestration only
- [ ] engine `update(context)` cleanup
- [ ] tests
- [ ] semgrep rules / policy updates

### UUL / DCP Gate (Blocking)
- [ ] `agent.step()` has no direct engine legacy calls (`update_from_*`, `generate_*`, `select_*`, `apply_*`, `infer_*`, `evaluate_*`)
- [ ] each engine called once via `update(context)` in UUL order
- [ ] `context.evolve(...)` done after each layer
- [ ] `world.step(...)` called once in world-step layer only

### Engine Contract Gate (Blocking)
- [ ] each migrated engine returns `snapshot`
- [ ] alignment/adjustments/trace outputs are explicit where applicable
- [ ] no duplicate state writes in the same step
- [ ] no hidden cross-engine mutation outside context flow

### Safety / Regression Gate
- [ ] `tests/test_context_propagation.py` passes
- [ ] affected NCA tests pass locally
- [ ] Semgrep Phase 12.1 workflow remains green
- [ ] no new blocker findings from `.semgrep/phase12_1_regression_scan.yml`

### Required Evidence
- [ ] before/after call-flow snippet for `agent.step()`
- [ ] list of removed legacy calls by file
- [ ] test run output included in PR comment
- [ ] explicit note of any deferred cleanup for Phase 12.3

### Risk Notes
State remaining risks, assumptions, and rollback plan.

