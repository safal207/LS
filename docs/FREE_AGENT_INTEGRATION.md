# Free Agent Integration

This page describes how to connect agents to LS without paid model API calls.

The goal is not to hide model cost. The goal is to make LS useful even when the
only available executors are:

- the current Codex session;
- a local model;
- deterministic LS checks;
- a human reviewer.

## Free-Only Principle

```text
models may be optional
LS artifacts are still mandatory
```

LS can still provide value by building a route artifact:

```text
git diff
-> selected route
-> review signals
-> role prompts
-> human/local-model outputs
-> contribution ledger later
```

## Option 1: Current Codex Session

Use the current Codex session as one role in the route.

```bash
python scripts/run_free_pr_review_route.py \
  --markdown-output reports/free_pr_review_route.md
```

Open the generated Markdown packet and paste one role prompt into Codex:

```text
draft_reviewer
risk_critic
evidence_verifier
final_reviewer
```

Codex performs the role, but LS remains the center that owns the artifact,
signals, route reward, and later contribution scoring.

## Option 2: Local Model

Run the same role prompts through a local model, for example Ollama.

The exact local-model command depends on the model installed on the machine, but
the contract is the same:

```text
role prompt in
JSON role output out
LS artifact remains the source of truth
```

## Option 3: Deterministic Only

If no model is available, run the deterministic artifact builder:

```bash
python scripts/run_pr_review_trail_artifact.py
```

This still gives:

- selected route;
- changed files;
- review signals;
- route reward;
- human-facing summary.

It is weaker than a full multi-role review, but it is free, reproducible, and
safe as a baseline.

## Option 4: Public CI Artifact

A public repository can run the artifact builder in CI and upload the Markdown
or JSON output as an artifact. This should remain advisory-only by default:

```text
PR opened
-> LS builds review artifact
-> maintainer reads artifact
-> human decides
```

Do not let free automation auto-merge or auto-approve code.

## Current Command

```bash
python scripts/run_free_pr_review_route.py
```

Save both JSON and Markdown:

```bash
python scripts/run_free_pr_review_route.py \
  --output reports/free_pr_review_route.json \
  --markdown-output reports/free_pr_review_route.md
```

For a branch-style review:

```bash
python scripts/run_free_pr_review_route.py \
  --base origin/main \
  --head my-feature-branch
```

## What This Gives Us

This lets LS test the cooperative route pattern before any paid integration:

```text
free executor
-> role output
-> LS artifact
-> route reward
-> later contribution score
```

The important product claim stays honest:

```text
LS does not require paid model calls to begin measuring cooperative precision.
```

