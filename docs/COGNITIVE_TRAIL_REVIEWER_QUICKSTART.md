# Cognitive Trail Reviewer Quickstart

Status: **working local research MVP**.

This quickstart is for grant reviewers, maintainers, and technical evaluators who
want to verify the LS Cognitive Trail Network without reading the full codebase.

Goal:

```text
clone -> install dependencies -> validate examples -> generate a trail run -> validate generated artifact -> inspect route stability proxy
```

Expected time: about 2 minutes after Python is available.

## What This Demonstrates

LS does not claim that it makes one model internally smarter.

This path demonstrates a narrower, testable claim:

```text
LS can record, validate, and repeat-measure which cooperative route made a concrete PR-review task more precise.
```

The smallest artifact is a **Cognitive Trail Run**:

```text
task
-> route of roles and actors
-> evidence
-> contribution attribution
-> result
-> repeatability decision
```

LS also includes a deterministic Nash-style route stability probe for checking
whether the full cooperative route beats simple counterfactuals.

Route-stability contract:

```text
docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md
```

Boundary:

```text
This is a route-stability proxy, not a formal proof of Nash equilibrium.
```

## 1. Validate Checked-in Trail Examples

Install validation and test dependencies:

```bash
python -m pip install jsonschema pytest
```

Run the contract validator:

```bash
python scripts/validate_cognitive_trail_runs.py
```

Expected output shape:

```text
Validated N cognitive trail run artifact(s) against schemas/cognitive_trail_run.schema.json.
- examples/trails/generated_pr_review_sample.json
- examples/trails/pr_review_cooperative_result.json
- examples/trails/pr_review_small_run.json
```

This checks both JSON Schema validity and LS-specific semantic invariants.

## 2. Inspect the Canonical Generated Sample

Open:

```text
examples/trails/generated_pr_review_sample.json
```

What to look for:

```text
baseline_reward:    0.5943
cooperative_reward: 0.7233
lift:               +0.1290
top_role:           risk_critic
top_actor:          gonka
decision:           repeat_with_more_diffs
```

Interpretation:

```text
The cooperative PR-review route improved the measured local benchmark signal in this sample.
It is not a global ranking of models or people.
```

## 3. Generate a Runtime Trail Run

Generate a local PR-review trail run from recent git history:

```bash
python scripts/generate_pr_review_trail_run.py --last 10
```

Default output:

```text
reports/trails/<timestamp>_pr_review_trail_run.json
```

Runtime reports are intentionally ignored by git:

```text
reports/trails/*.json
```

The directory itself is kept by:

```text
reports/trails/.gitkeep
```

## 4. Generate and Validate in One Pass

Run:

```bash
python scripts/generate_pr_review_trail_run.py --last 10 --validate
```

Expected output shape:

```text
Validated 1 cognitive trail run artifact(s) against schemas/cognitive_trail_run.schema.json.
- reports/trails/<timestamp>_pr_review_trail_run.json
Generated LS Cognitive Trail Run
Output: reports/trails/<timestamp>_pr_review_trail_run.json
Lift: +...
Top role: ...
Top actor: ...
Validation: passed
```

This is the core loop:

```text
artifact born -> artifact checked -> artifact ready for trail network reuse
```

## 5. Generate a Human-Readable Markdown Report

Run:

```bash
python scripts/generate_pr_review_trail_run.py \
  --last 10 \
  --validate \
  --markdown-output reports/trails/pr_review_trail_run_report.md
```

This writes two artifacts:

```text
reports/trails/<timestamp>_pr_review_trail_run.json
reports/trails/pr_review_trail_run_report.md
```

The JSON file remains the canonical machine-checkable Cognitive Trail Run. The
Markdown file is a reviewer-facing report with summary, result, route, evidence,
contribution summary, repeatability, and non-claims.

## 6. Check Nash-Style Route Stability

Inspect the route-stability contract:

```text
docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md
```

Inspect the checked-in route-stability schema and sample:

```text
schemas/route_stability_sample.schema.json
examples/route-stability/nash_route_stability_sample.json
```

Run:

```bash
python scripts/run_nash_route_stability_demo.py
```

For a machine-readable artifact, run:

```bash
python scripts/run_nash_route_stability_demo.py --json > reports/trails/nash_route_stability.json
```

Current expected local result:

```text
full route:          pr_review>local>gonka>mimo
reward:              0.7863
single baseline:     0.1207
coalition gain:      +0.6656
best counterfactual: pr_review>local>gonka = 0.5613
stability margin:    +0.2250
decision:            stable_candidate
```

Participant marginal contributions:

```text
local: +0.3226
gonka: +0.2913
mimo:  +0.2250
```

Interpretation:

```text
The full cooperative route currently beats the single-route baseline, participant ablations, and a bad ordering counterfactual.
```

Boundary:

```text
This is a Nash-style route stability proxy, not a formal proof of Nash equilibrium.
```

Regression check:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
```

This test validates the checked-in sample against `schemas/route_stability_sample.schema.json`
and pins it against the deterministic `--json` output for stable fields such as
route rewards, counterfactuals, marginal contributions, thresholds, and
interpretation boundary.

## 7. Inspect CI-Generated Report Artifacts

The `Cognitive Trail Contract` workflow also generates reviewer artifacts in CI.

Workflow path:

```text
.github/workflows/cognitive_trail_contract.yml
```

The workflow uploads a GitHub Actions artifact named:

```text
cognitive-trail-report-${{ github.sha }}
```

The artifact contains:

```text
reports/trails/ci/cognitive_trail_run.json
reports/trails/ci/cognitive_trail_run_report.md
reports/trails/ci/nash_route_stability.json
```

Reviewer interpretation:

```text
CI validates checked-in examples, runs generator and negative validation tests, tests the Nash-style route stability probe, generates a fresh runtime trail run, validates it, generates a Nash-style stability JSON artifact, and exposes all reviewer artifacts for download.
```

The uploaded Cognitive Trail JSON is machine-checkable. The uploaded Markdown is
intended for human review and PR/grant discussion. The uploaded Nash-style
stability JSON is a route-stability proxy artifact, not a formal game-theoretic
proof.

## 8. Validate One Specific Generated Artifact

If a runtime report already exists, validate only that file:

```bash
python scripts/validate_cognitive_trail_runs.py \
  --example reports/trails/<timestamp>_pr_review_trail_run.json
```

## 9. Check Negative Validation Behavior

The test suite also verifies that invalid artifacts fail.

Run:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_generate_pr_review_trail_run.py
```

Current negative checks include:

```text
unknown top-level schema field                   -> rejected by JSON Schema
inconsistent result.lift                         -> rejected by semantic validator
contribution_summary/result attribution mismatch -> rejected by semantic validator
route.step gap or non-contiguous route           -> rejected by semantic validator
```

This is intentional. A Cognitive Trail artifact should not be accepted merely
because it is valid JSON. It must match the strict schema and preserve semantic
consistency across route, evidence, result, contribution, route ordering, and
repeatability fields.

## What the Validator Checks

The validator enforces:

- all target files are valid JSON;
- the schema is valid Draft 2020-12 JSON Schema;
- every target file matches `schemas/cognitive_trail_run.schema.json`;
- `lift == cooperative_reward - baseline_reward`;
- `positive_lift` matches the sign of `lift`;
- route steps are contiguous from `1`;
- `top_role` is present in the recorded route;
- `top_actor` is present in the recorded route;
- `contribution_summary.top_role` matches `result.top_role`;
- `contribution_summary.top_actor` matches `result.top_actor`.

## Reviewer Interpretation

A positive trail run means:

```text
This route improved the measured task signal for this local benchmark run.
```

A stable-candidate Nash-style route stability probe means:

```text
This full cooperative route beat the configured single-route baseline, participant ablations, and bad-ordering counterfactual for this deterministic local probe.
```

It does **not** mean:

```text
This actor is globally best.
This role should always dominate.
This is a formal Nash equilibrium proof.
LS already has a global live network.
The system may act without human authority.
```

## Key Files

```text
docs/COGNITIVE_TRAIL_RUN_CONTRACT.md
docs/COGNITIVE_TRAIL_SCHEMA_VERSIONING.md
docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md
docs/COOPERATIVE_PRECISION_METRICS.md
schemas/cognitive_trail_run.schema.json
schemas/route_stability_sample.schema.json
examples/trails/generated_pr_review_sample.json
examples/route-stability/nash_route_stability_sample.json
scripts/validate_cognitive_trail_runs.py
scripts/generate_pr_review_trail_run.py
scripts/run_nash_route_stability_demo.py
python/tests/test_generate_pr_review_trail_run.py
python/tests/test_nash_route_stability.py
.github/workflows/cognitive_trail_contract.yml
```

## Why This Matters

Most AI productivity tools save outputs.

LS is trying to save and validate the route that produced a better output:

```text
which task
which route
which evidence
which contribution
which result
whether to repeat
whether the route stays stronger than simple counterfactuals
```

That is the first operational form of the **Cognitive Trail Network**.
