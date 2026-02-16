## Phase 12.3 PR Checklist

### Objective
Complete migration to context-single-source architecture for NCA loop.

### Orchestration Gate (Blocking)
- [ ] `agent.step()` calls engines only via `update(context)`.
- [ ] No direct legacy prefixes in `agent.step()`:
  - `update_from_*`
  - `generate_*`
  - `select_*`
  - `apply_*`
  - `infer_*`
  - `evaluate_*`
- [ ] `world.step(...)` occurs once, in world-step layer only.

### Engine Gate (Blocking)
- [ ] Each engine `update(context)` uses context as input contract.
- [ ] No cross-engine legacy calls in pipeline flow.
- [ ] No duplicated alignment/trace/evolve logic outside owning update.
- [ ] Engine return payload includes `snapshot` and layer-specific fields.

### Context Gate (Blocking)
- [ ] Snapshot fields are advanced only via `context.evolve(...)` in step.
- [ ] No manual out-of-band snapshot mutation.
- [ ] `UpdateContext` fields are reviewed for usage and redundancy.

### Policy / CI Gate
- [ ] Phase 12.1 Semgrep workflow green.
- [ ] Phase 12.2 ruleset checked for migration debt.
- [ ] Phase 12.3 ruleset checked and findings handled as planned.
- [ ] DCP tests pass (`tests/test_context_propagation.py`).

### Evidence
- [ ] before/after `step()` call-flow snippet
- [ ] list of removed legacy calls by file
- [ ] test output attached
- [ ] known deferred items (if any) documented

