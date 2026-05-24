# Depth Economy Layer

Status: **concept-to-probe architecture note**.

Depth Economy is the LS layer for deciding how deep a task must go before it is
executed, remembered, or turned into reputation.

It extends the role chain:

```text
customer -> consumer -> designer -> executor -> critic -> verifier -> operator -> memory
```

with recursive customer-consumer depth:

```text
customer L1 -> consumer L1
customer L2 -> consumer L2
customer L3 -> consumer L3
...
customer Ln -> consumer Ln
```

## Core Formula

Different roles operate with different coordination math:

```text
executor:            1 + 1 = 2
designer:            1 + 1 = 3
customer / consumer: 1 + 1 = n
```

Meaning:

- `1+1=2` is correctness: do the clear thing exactly.
- `1+1=3` is design synergy: compose parts so the route creates extra value.
- `1+1=n` is depth economics: choose the customer-consumer level where the
  value, risk, and affected consumers are represented correctly.

## Why This Exists

Many agent failures happen because a task is handled at the wrong depth.

Examples:

- a level-1 executor answers a level-3 social or safety question;
- a designer tries to create synergy before the consumer is defined;
- a high-risk memory/action update is treated like a simple text answer;
- a model claims value without knowing who receives the value.

Depth Economy asks first:

```text
At what depth should this decision be made?
```

## Depth Levels

| Level | Name | Customer | Consumer | Key question |
| --- | --- | --- | --- | --- |
| L1 | Direct task | Immediate request owner | Immediate user | Can this be executed correctly now? |
| L2 | Product value | Product or workflow owner | Workflow user or team | Will this improve the user's real workflow? |
| L3 | Systemic impact | System steward | Affected community or ecosystem | What second-order effects does this create? |
| L4 | Long-horizon stewardship | Long-horizon steward | Future maintainers and downstream users | Should this shape future behavior? |

Future versions can add more levels, but the first probe keeps the ladder small
and testable.

## Amygdala Role

Amygdala is the bio-inspired salience and protection regulator for depth.

It does not decide truth or morality. It controls whether the system should:

- execute directly;
- design for synergy;
- deepen the customer-consumer pair;
- expand the stakeholder radius;
- narrow to evidence and execution;
- hold until human review.

Signals:

```text
task_importance
risk_pressure
uncertainty
care_expansion
evidence_gap
reversibility
amygdala_pressure
```

High risk, high evidence gap, high irreversibility, or high Amygdala pressure
push the system deeper or into human review. Clear, reversible, low-risk tasks
stay shallow.

## Relation To Nash-Style Route Stability

Nash-style route stability asks:

```text
Does this cooperation route beat single-route and ablation counterfactuals?
```

Depth Economy asks:

```text
What depth of customer-consumer pair is required before a route should run?
```

Together:

```text
Depth Economy chooses the level.
Nash-style stability tests whether the route was worth repeating.
Trail memory remembers the verified route.
```

## Deterministic Probe

Run:

```bash
python scripts/run_depth_economy_demo.py
python scripts/run_depth_economy_demo.py --json
```

Expected shape:

```text
low_risk_fix -> L1 -> 1+1=2 -> execute_directly
product_route_design -> L2/L3 -> 1+1=3 or n -> design/deepen
high_stakes_memory_or_action -> L4 -> 1+1=n -> hold_until_human_review
```

Regression test:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_depth_economy_demo.py
```

## Model Roster Probe

Depth decisions should know which actors are actually available. Run:

```bash
python scripts/run_model_roster_depth_probe.py --json
PYTHONPATH=.:python:python/modules python scripts/run_model_roster_depth_probe.py --live --json
```

See:

- `docs/MODEL_ROSTER_DEPTH_PROBE.md`

This separates the LS actor roster from live runtime readiness: local Qwen can
handle shallow checks, while deeper L2-L4 decisions should stay under Codex or
human review unless stronger configured backends are available.

## Interpretation Boundary

Depth Economy is not:

- a claim of consciousness;
- a formal economic theorem;
- a replacement for human judgment;
- a neuroscience claim about real biological amygdala function.

It is a coordination-depth probe for deciding whether a task should be executed,
designed, deepened, or held.

## One-Line Claim

```text
LS does not only choose a route; it chooses the depth at which the route should
be allowed to exist.
```
