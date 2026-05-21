# PR Role Market Benchmark

This note explains the first small benchmark for the LS PR Role Market.

It is meant to be readable in 30 seconds by a reviewer or contributor.

## What Was Measured

LS compared two ways to review recent git diffs:

```text
baseline:
  pr_review>direct_single_reviewer

cooperative route:
  pr_review>draft_reviewer>risk_critic>evidence_verifier>final_reviewer
```

The question was not "which model is globally best?"

The question was narrower:

```text
Does a cooperative role route produce a better review signal than one direct pass?
Which role contributed the most value in this context?
Which existing LS actor/model was assigned to that role?
```

## Current Snapshot

Command:

```bash
python scripts/run_pr_role_market_batch.py --last 3
```

Observed result:

```text
Analyzed: 3/3
Errors: 0
Average baseline reward: 0.5943
Average cooperative reward: 0.7233
Average reward lift: +0.1290
Positive reward lift: 3/3
Top role: risk_critic (3)
Top actor: gonka (3)
```

With attached sample role outputs:

```bash
python scripts/run_pr_role_market_batch.py \
  --last 3 \
  --role-outputs docs/examples/pr_role_outputs.sample.json
```

Observed result:

```text
Analyzed: 3/3
Errors: 0
Attached role outputs: true
Average reward lift: +0.1290
Positive reward lift: 3/3
Top role: risk_critic (3)
Top actor: gonka (3)
```

## Plain-English Interpretation

On this small sample, LS found that a role-based review route beat the direct
single-reviewer baseline on every checked diff.

The most useful role was `risk_critic`.

That means the current diffs benefited most from a role that looks for risk:

- large diffs;
- missing tests;
- unsafe changes;
- weak evidence;
- places where a human should slow down before merge.

The top actor was `gonka` because the current LS roster assigns `gonka` to the
`risk_critic` role.

## Actor Roster Boundary

The benchmark only names actors already present in this repository/config:

```text
codex-self-use
local-qwen / qwen2.5:7b
local-qwen-light / qwen2.5:1.5b
gonka / qwen/qwen3-235b-a22b-instruct-2507-fp8
mimo / mimo-v2-flash
human_operator
```

Unknown actors are rejected by the role-output parser. This keeps the report
honest: LS cannot silently claim that unsupported models participated.

## What This Proves

It proves that LS can already measure a useful local loop:

```text
git diff
-> direct baseline
-> cooperative role route
-> reward lift
-> best role
-> assigned actor/model
-> repeat over history
```

The important result is not that one actor is permanently "best".

The important result is:

```text
LS can measure which cooperation pattern made a concrete task more precise.
```

## What This Does Not Prove Yet

This is not a broad scientific benchmark yet.

Current limitations:

- sample size is small;
- scoring is deterministic and heuristic;
- attached role outputs are sample artifacts unless replaced with real actor outputs;
- CI, human review comments, and post-merge outcomes are not yet included;
- the result is contextual, not a hidden global ranking of people or models.

## How To Reproduce

Single diff:

```bash
python scripts/run_pr_role_market_demo.py
```

Single diff with attached role outputs:

```bash
python scripts/run_pr_role_market_demo.py \
  --role-outputs docs/examples/pr_role_outputs.sample.json
```

Recent history:

```bash
python scripts/run_pr_role_market_batch.py --last 10
```

Recent history with a Markdown report:

```bash
python scripts/run_pr_role_market_batch.py \
  --last 10 \
  --role-outputs docs/examples/pr_role_outputs.sample.json \
  --markdown-output reports/role_market/pr_role_market_history.md
```

## What Contributors Can Improve

Good next contributions:

- add small diff fixtures for docs-only, missing-tests, large-diff, and unsafe-command cases;
- attach real role outputs from `codex-self-use`, local Qwen, or human review;
- add CI/test outcome signals to the reward calculation;
- compare route performance over more commits;
- improve the Markdown report so it can be pasted into a PR;
- add a GitHub Action that uploads the report as an advisory artifact.

## One-Line Claim

```text
LS measures which cooperative role made a PR review more precise.
```
