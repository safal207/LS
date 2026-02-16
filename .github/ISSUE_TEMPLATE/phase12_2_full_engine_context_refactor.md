name: "Phase 12.2: Full Engine Context Refactor"
about: "Migrate NCA engines to strict update(context) API and remove legacy calls from step()"
title: "[Phase 12.2] Full Engine Context Refactor"
labels: ["enhancement", "architecture", "nca"]
assignees: ""

---

## Objective
Move NCA to a strict deterministic update pipeline:
- `agent.step()` must orchestrate only `update(context)` calls per engine.
- Engine internals must stop using mixed legacy API in `update(context)`.
- Preserve UUL v1.0 order and deterministic context propagation.

## Scope
- `python/modules/nca/agent.py`
- `python/modules/nca/{identity_core,social_cognition,culture_engine,militocracy_engine,synergy_engine,value_system,autonomy_engine,intent_engine}.py`
- `.semgrep/phase12_2_legacy_api_ban.yml`
- tests that validate step ordering and context propagation

## Non-Goals
- No redesign of planner scoring model.
- No behavior re-tuning beyond refactor-driven parity fixes.
- No unrelated API renames outside NCA engine boundary.

## Required Engine Contract
Each engine exposes:
```python
def update(self, context: UpdateContext) -> dict[str, Any]:
    ...
    return {
        "snapshot": ...,
        "alignment": ...?,      # if applicable
        "adjustments": ...?,    # if applicable
        "trace_snapshot": ...?, # if applicable
    }
```

## Acceptance Criteria
- `agent.step()` contains no legacy direct engine calls:
  - no `update_from_*`
  - no `generate_*`
  - no `select_*`
  - no `apply_*`
  - no `infer_*`
  - no `evaluate_*`
- `world.step(...)` is called exactly once and only in world-step layer.
- Every engine is called exactly once via `update(context)` in UUL order.
- `context.evolve(...)` is used after each layer update.
- Phase 12.1 Semgrep workflow stays green.
- `tests/test_context_propagation.py` passes.

## Engine-by-Engine Tasks
- [ ] IdentityCore: consolidate to `update(context)` and context snapshot output.
- [ ] SocialCognition: consolidate collective + inference + alignment + adjustments in `update(context)`.
- [ ] CultureEngine: consolidate social/values/collective integration + norms + alignment in `update(context)`.
- [ ] MilitocracyEngine: consolidate identity/autonomy/culture + trace in `update(context)`.
- [ ] SynergyEngine: consolidate social/culture/collective + trace in `update(context)`.
- [ ] ValueSystem: consolidate identity/collective/intents/autonomy + alignment + drift in `update(context)`.
- [ ] AutonomyEngine: keep full strategy cycle inside `update(context)`.
- [ ] IntentEngine: keep full intent cycle inside `update(context)`.

## Validation Plan
- [ ] `python -m pytest tests/test_context_propagation.py -q`
- [ ] targeted NCA tests (step/event invariants)
- [ ] Semgrep phase12.1 workflow green
- [ ] Phase12.2 ruleset reviewed for expected findings trend

