# Agent Development Roadmap (3–6 Months)

This document formalizes the proposed 3–6 month roadmap into an execution plan with milestones, measurable outcomes, and implementation checkpoints.

## North Star

By the end of the roadmap, the agent should:

- choose actions from alternative scenarios with measurable quality,
- improve strategy quality based on historical outcomes,
- execute useful external-tool actions safely,
- expose transparent KPI dashboards for continuous optimization,
- support productization toward commercial outcomes.

## Phase 1 — Integration and Stable Pipeline (Month 1)

### Goal
Create a single end-to-end decision loop from incoming event to selected action.

### Implementation steps

1. Integrate `CounterfactualEngine` + `StrategyEvolutionEngine` into one orchestration loop.
2. Log each action decision and outcome into `cognitive_state`.
3. Add baseline metrics:
   - `confidence`
   - `predicted_outcome`
   - action success flag / score
4. Add integration tests for representative scenarios:
   - straightforward positive outcome
   - conflicting strategies
   - low-confidence fallback path

### Exit criteria

- The loop executes automatically without manual hand-offs.
- For every action, prediction + actual outcome are recorded.
- Integration tests pass for all baseline scenarios.

---

## Phase 2 — Cognitive State Expansion and Learning (Months 1–2)

### Goal
Enable adaptive behavior and strategy refinement through feedback.

### Implementation steps

1. Add long-form action history with timestamped outcomes.
2. Introduce long-term strategy performance metrics (profit / efficiency / task yield).
3. Expand `causal_edges` based on observed real-world outcomes.
4. Add confidence recalibration and overestimated-strategy filtering.

### Exit criteria

- Strategy ranking incorporates both short-term and long-term performance.
- Confidence updates are data-driven rather than static.
- Repeatedly underperforming strategies are down-weighted automatically.

---

## Current status snapshot

- **Phase 1–2:** Functionally closed (integration loop + learning baseline are in place).
- **Phase 3:** Core runtime guardrails are implemented (timeouts, retries, circuit, audit), but tool integrations are still mostly local.
- **Phase 4:** Simulation and baseline comparison exist, but the gate is not yet hard-enforced in lifecycle promotion.
- **Phase 5:** Replay/trends primitives exist at backend level; operator-facing endpoint/UI layer is still required.

---

## Phase 3 — Real Tool Adapters and Production Integrations (Months 2–4)

### Goal
Move from local tool stubs to production-grade external integrations with a unified runtime contract.

### Implementation steps

1. Introduce a `ToolAdapter` interface contract:
   - `name()`
   - `healthcheck()`
   - `execute(request)`
2. Add at least two production adapters:
   - HTTP context adapter (external context/API retrieval)
   - data adapter (structured data access or write path)
3. Integrate adapters into `ToolRuntime` via adapter registry (not direct local-function binding).
4. Add healthcheck scheduler:
   - passive checks (based on runtime failures)
   - active checks (periodic probe)
5. Add health-based degradation policy:
   - route away from unhealthy adapters
   - deterministic fallback_reason logging

### Exit criteria

- Tool execution path is adapter-driven and contract-consistent.
- At least 1–2 real external integrations run under runtime guardrails.
- Health degradation and fallback are automated and observable.

---

## Phase 4 — Simulation Gate Enforcement in Lifecycle (Month 4–5)

### Goal
Make simulation evaluation a mandatory promotion gate for strategy lifecycle changes.

### Implementation steps

1. Define explicit acceptance policy for promotion (example defaults):
   - `success_rate_delta >= 0`
   - `prediction_accuracy_delta >= -0.01`
   - `average_value_delta >= 0`
2. Enforce `evaluate_strategy_candidate` gate before any promote action.
3. Add `manual_override_reason` to gate result model.
4. Persist complete decision history in `strategy_gate_history` (not only `last_strategy_gate`).
5. Feed gate outcomes and deltas back into strategy evolution loops.

### Exit criteria

- No strategy reaches promotion path without gate evaluation.
- Overrides are explicit, auditable, and reasoned.
- Gate decisions are historically queryable for trend analysis.

---

## Phase 5 — Operator Surface (Month 5–6)

### Goal
Expose thin but operationally useful interface endpoints over existing replay/trends primitives.

### Implementation steps

1. Add operator-facing endpoints:
   - `GET /agent/snapshot`
   - `GET /agent/replay`
   - `POST /agent/controls`
2. Expand trends with tool-specific reliability KPI:
   - timeout rate
   - circuit-open rate
   - adapter-level error rate
3. Add top failure clusters:
   - grouped by `fallback_reason`
   - grouped by `tool_execution.error`
4. Keep UI/API thin; prioritize production diagnostics over heavy UX buildout.

### Exit criteria

- Operators can retrieve state, replay decisions, and apply controls through stable endpoints.
- Tool/runtime failures are visible in ranked clusters for faster incident triage.
- Reliability trends support weekly operational reviews.

---

## Priority sprint plan (1–2 weeks)

### Week 1

1. Implement `ToolAdapter` contract and wire adapter registry into `ToolRuntime`.
2. Ship first real adapter and add second adapter stub/integration target.
3. Add active+passive healthchecks and degradation policy.

### Week 2

1. Enforce gate acceptance policy + add `strategy_gate_history` persistence.
2. Add `manual_override_reason` support in gate flows.
3. Deliver `snapshot/replay/controls` endpoints.
4. Extend observability metrics for timeout/circuit degradation trends.

---

## Cross-phase KPI framework

Track these KPIs across all phases:

- Decision quality: success rate, regret score vs. best counterfactual.
- Prediction quality: `predicted_outcome` calibration error.
- Learning quality: improvement slope over rolling windows.
- Tool reliability: success/timeout/error rates by integration.
- Business value: value-per-action and monthly impact trend.

## 6-Month expected outcome

At roadmap completion, the agent should be a self-improving decision system that:

- evaluates alternative scenarios,
- learns from historical outcomes,
- applies tools/APIs in real workflows,
- proves effectiveness through transparent KPIs,
- is suitable as a foundation for a monetizable product line.
