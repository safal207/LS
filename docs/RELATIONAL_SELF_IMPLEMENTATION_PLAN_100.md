# Relational Self — 100% Implementation Plan

## Objective
Deliver a production-grade Relational Self capability that is:
1. **Deterministic** in synthesis and council outcomes.
2. **Governed** by explicit constitutional invariants.
3. **Explainable** for operators and end users.
4. **Observable** through MCP + metrics.
5. **Safe** through rollback and escalation policies.

---

## Scope baseline (already done)
- RelationalSelf model + persistence.
- Coherence history snapshots.
- Council modes (`self-consistency-check`, `self-evolution-proposal`, `self-preservation`).
- Constitution foundation + tests.
- MCP resources (`self/relational-self`, `self/coherence-history`) and `ask_self` tool.

---

## Phase A — Constitution Completion (P0)

### A1. Rule schema + versioning
**Files**
- `python/modules/council/self_constitution.py`
- `python/modules/graph/models.py`

**Tasks**
- Add explicit constitution schema version and migration path.
- Add rule IDs and stable reason codes.
- Add severity semantics: `warn`, `block`, `escalate` with deterministic precedence.

**Definition of Done**
- Every finding has stable (`rule_id`, `reason_code`, `severity`, `passed`).
- Backward compatibility preserved for existing payload consumers.

---

### A2. Constitution event ledger
**Files**
- `python/modules/graph/memory_store.py`
- `python/modules/council/cycle_runner.py`

**Tasks**
- Persist per-cycle constitution evaluations in JSONL ledger.
- Store links: `cycle_id`, `snapshot_id`, `blocked`, `severity_summary`.

**Definition of Done**
- New `constitution_history` retrievable with limit/filter.
- Council cycle output includes ledger artifact path/id.

---

## Phase B — Explainability (P0)

### B1. Causal explanation graph
**Files**
- `python/ls/agent_shell/cognitive_state.py`
- `python/modules/council/cycle_runner.py`

**Tasks**
- Extend `ask_self` to return cause chain:
  - `events` -> `relation_shift` -> `coherence_delta` -> `applied_action`.
- Include top violating constitution rules and recovered rules.

**Definition of Done**
- `ask_self` response contains `causal_trace` array.
- Response stable for missing/partial histories.

---

### B2. Human-readable operator summary
**Files**
- `python/ls/agent_shell/mcp_resources.py`
- `python/ls/agent_shell/cognitive_state.py`

**Tasks**
- Add resource `self/constitution-status`.
- Add compact summary fields:
  - `identity_state` (`stable`, `drifting`, `at-risk`),
  - `breach_risk`,
  - `last_action_effect`.

**Definition of Done**
- MCP clients can fetch status without custom post-processing.

---

## Phase C — Safe Autonomy (P0/P1)

### C1. Action policy gates
**Files**
- `python/modules/council/cycle_runner.py`
- `python/modules/council/council_engine.py`

**Tasks**
- Add policy matrix for auto-apply vs review-required.
- Require review for actions under constitution `escalate` failures.

**Definition of Done**
- No action auto-applied if escalate conditions are present.
- Explicit `policy_decision` returned in cycle output.

---

### C2. Rollback plan for each action
**Files**
- `python/modules/council/cycle_runner.py`
- `python/modules/graph/memory_store.py`

**Tasks**
- Persist before/after snapshots for applied actions.
- Add rollback API by `action_id`.

**Definition of Done**
- Any applied action can be rolled back with deterministic state restoration.

---

## Phase D — Observability & Reliability (P1)

### D1. Metrics
**Files**
- `python/modules/council/*`
- `python/ls/agent_shell/cognitive_state.py`

**Metrics**
- `self_coherence_score`
- `constitution_violation_count`
- `auto_action_apply_rate`
- `rollback_rate`
- `mean_recovery_cycles`

**Definition of Done**
- Metrics emitted per cycle and queryable through MCP/resource snapshots.

---

### D2. Robustness tests
**Files**
- `python/tests/test_self_constitution.py`
- `python/tests/test_council_self_integration.py`
- `python/tests/test_cognitive_self_mcp.py`
- `python/tests/test_relational_self.py`

**Test additions**
- malformed JSONL rows,
- missing timestamps,
- race-like updates,
- long-history truncation behavior,
- rollback integrity.

**Definition of Done**
- Negative and edge cases covered with deterministic expected outputs.

---

## Delivery order (recommended)
1. A1
2. A2
3. B1
4. C1
5. B2
6. C2
7. D1
8. D2

---

## Acceptance criteria for “100% complete”
- Constitution + ledger + explainability + policy-gated actioning + rollback implemented.
- MCP surfaces expose current status, history, and causal trace.
- All tests (happy-path + negative-path) pass in CI.
- No breaking changes for existing MCP consumers.

---

## Risk register
- **Risk:** over-blocking due to aggressive thresholds.  
  **Mitigation:** staged thresholds + telemetry-driven tuning.
- **Risk:** action loops causing oscillation.  
  **Mitigation:** cooldown windows + rollback + hysteresis.
- **Risk:** payload drift for external tools.  
  **Mitigation:** schema versioning + compatibility adapters.
