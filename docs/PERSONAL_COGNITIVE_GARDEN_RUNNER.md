# Personal Cognitive Garden Demo Runner

This runner package provides a minimal local demonstration of the Personal Cognitive Garden artifact flow.

It is intentionally dependency-free and uses checked-in examples so grant reviewers can reproduce the core safety claims without a backend service.

## 1. Run the core PCG artifact demo

```bash
python3 scripts/run_personal_cognitive_garden_demo.py
```

Machine-readable output:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py --json
```

Custom example directory:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py \
  --example-dir examples/personal_cognitive_garden
```

## 2. Run the anti-surveillance red-team demo

This addresses the highest-risk misuse scenario for Personal Cognitive Garden: employer or third-party access to a person's private cognitive graph.

```bash
python3 scripts/run_pcg_red_team.py
```

Machine-readable output:

```bash
python3 scripts/run_pcg_red_team.py --json
```

Expected decision:

```text
Decision: BLOCK
Reason: PRIVATE_GRAPH_ACCESS_REQUEST
External action allowed: False
```

The runner reads:

```text
examples/personal_cognitive_garden/red_team_employer_surveillance_request.json
```

## 3. Run the evaluation harness

This small synthetic harness checks whether the PCG reviewer path can distinguish sessions that should create human-reviewed development updates from sessions that should not become durable claims about a person.

```bash
python3 scripts/run_pcg_evaluation.py
```

Machine-readable output:

```bash
python3 scripts/run_pcg_evaluation.py --json
```

The harness reads:

```text
examples/personal_cognitive_garden/evaluation_sessions.json
```

It covers these session classes:

- `emotional_support`
- `administrative`
- `decision_clarification`
- `skill_building`
- `capital_compounding`
- `execution`
- `noise`

## 4. Run regression tests

```bash
PYTHONPATH=. pytest tests/test_pcg_grant_evidence_artifacts.py
```

These tests verify:

- the employer-surveillance request is blocked;
- synthetic developmental-session classification stays stable;
- proposed updates do not become durable state before review;
- accepted updates require review and remain private by default;
- fixture JSON remains machine-readable.

## What the core demo reads

```text
examples/personal_cognitive_garden/session_summary.json
examples/personal_cognitive_garden/proposed_update.json
examples/personal_cognitive_garden/accepted_graph_state.json
```

## Gateway-to-garden before/after example

For a compact raw-agent-output example, see:

```text
docs/PERSONAL_COGNITIVE_GARDEN_GATEWAY_BEFORE_AFTER.md
examples/personal_cognitive_garden/gateway_to_garden_before_after.json
```

It shows one accepted update and one held/rejected update without making
benchmark claims.

## What the core demo demonstrates

```text
session summary
-> development classification
-> skill delta
-> capital effect
-> practice needed
-> governance review
-> accepted graph nodes
```

## Expected human-readable output

The core runner prints:

- session id and type;
- development class;
- whether the session is developmental;
- human skill deltas;
- capital effect;
- practice needed;
- compounding score;
- proposed status;
- review decision;
- accepted graph nodes;
- the human-capital invariant.

## Invariant

> A session may inform memory, but only developmental sessions should compound human-owned skill capital.

## Anti-surveillance invariant

> The person owns the cognitive garden. External systems may only receive explicitly consented, evidence-backed, non-sensitive views.

## Non-goal

This is not yet the production PCG engine. It is a local reproducibility shim for the checked-in schema, examples, red-team scenario, and evaluation harness.
