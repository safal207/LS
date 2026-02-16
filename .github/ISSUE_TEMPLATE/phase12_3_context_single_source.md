name: "Phase 12.3: Context As Single Source of Truth"
about: "Complete NCA migration so step() is orchestration-only and engines are fully context-driven."
title: "[Phase 12.3] Context single-source migration"
labels: ["enhancement", "architecture", "nca", "phase12.3"]
assignees: ""

---

## Goal
Make `UpdateContext` the only state contract used by the NCA decision loop.

After completion:
- `agent.step()` is a thin orchestrator.
- Engines use `update(context)` as the only integration surface.
- Legacy engine calls are removed from pipeline flow.
- No duplicated alignment/evolve/trace computation across layers.

## Hard Invariants
- No `update_from_*` calls in `agent.step()`.
- No direct `generate_*`, `select_*`, `apply_*`, `infer_*`, `evaluate_*` calls in `agent.step()`.
- No cross-engine legacy calls in update pipeline.
- Engine output is explicit (`snapshot` plus layer-specific fields).
- `context.evolve(...)` is the only way snapshots are advanced in step pipeline.

## Scope
- `python/modules/nca/agent.py`
- NCA engines:
  - `identity_core.py`
  - `social_cognition.py`
  - `culture_engine.py`
  - `militocracy_engine.py`
  - `synergy_engine.py`
  - `value_system.py`
  - `autonomy_engine.py`
  - `intent_engine.py`
- `python/modules/nca/update_context.py`
- `.semgrep/phase12_3_context_single_source.yml`

## Acceptance Criteria
- [ ] `agent.step()` contains only orchestration + planning + world step + finalization.
- [ ] Layer order matches UUL v1.0.
- [ ] No duplicated metrics/alignment/evolve logic outside owning engine update.
- [ ] Engine update contracts are stable and context-only.
- [ ] DCP tests pass.
- [ ] Semgrep Phase 12.1, 12.2, 12.3 policies pass expected gates.

## Validation
- [ ] `python -m pytest tests/test_context_propagation.py -q`
- [ ] selected NCA tests for behavior parity
- [ ] static scan with Phase 12.3 ruleset

