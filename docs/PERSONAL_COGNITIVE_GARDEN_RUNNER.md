# Personal Cognitive Garden Demo Runner

This runner provides a minimal local demonstration of the Personal Cognitive Garden artifact flow.

It is intentionally dependency-free and uses only checked-in examples.

## Run

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

## What it reads

```text
examples/personal_cognitive_garden/session_summary.json
examples/personal_cognitive_garden/proposed_update.json
examples/personal_cognitive_garden/accepted_graph_state.json
```

## What it demonstrates

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

The runner prints:

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

> A session may inform memory, but only developmental sessions should compound human capital.

## Non-goal

This is not yet the production PCG engine. It is a local reproducibility shim for the checked-in schema and example artifacts.
