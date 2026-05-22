# Cognitive Trail Contributor Tasks

Status: **working local research MVP**.

This is a focused contributor task list for hardening the LS Cognitive Trail
contract and PR-review benchmark path.

The goal is to help contributors improve one narrow evidence chain:

```text
PR diff
-> cooperative route
-> evidence
-> contribution attribution
-> benchmark result
-> Cognitive Trail Run artifact
-> validator
-> CI
-> downloadable JSON/Markdown report artifact
```

## Start Here

Read these first:

- [`COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md`](COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md)
- [`COGNITIVE_TRAIL_RUN_CONTRACT.md`](COGNITIVE_TRAIL_RUN_CONTRACT.md)
- [`COGNITIVE_TRAIL_SCHEMA_VERSIONING.md`](COGNITIVE_TRAIL_SCHEMA_VERSIONING.md)
- [`COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md`](COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md)
- [`PR_ROLE_MARKET_BENCHMARK.md`](PR_ROLE_MARKET_BENCHMARK.md)
- [`../examples/trails/generated_pr_review_sample.json`](../examples/trails/generated_pr_review_sample.json)

Run these checks before opening a PR:

```bash
python -m pip install jsonschema pytest
python scripts/validate_cognitive_trail_runs.py
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_generate_pr_review_trail_run.py
```

Optional runtime generation check:

```bash
python scripts/generate_pr_review_trail_run.py \
  --last 10 \
  --validate \
  --markdown-output reports/trails/pr_review_trail_run_report.md
```

## CI Report Artifact

The `Cognitive Trail Contract` workflow generates and uploads reviewer artifacts.

Workflow:

```text
.github/workflows/cognitive_trail_contract.yml
```

Artifact name:

```text
cognitive-trail-report-${{ github.sha }}
```

Artifact contents:

```text
reports/trails/ci/cognitive_trail_run.json
reports/trails/ci/cognitive_trail_run_report.md
```

The JSON file is the canonical machine-checkable report. The Markdown file is the
human-readable reviewer report.

## Contributor Rules

Keep the benchmark honest:

- do not claim global model ranking;
- do not claim production-grade evaluation;
- keep role and actor separate;
- keep small samples marked `needs_more_runs: true`;
- do not commit local runtime files under `reports/trails/*.json`;
- commit only curated examples under `examples/trails/`;
- if schema semantics change, follow [`COGNITIVE_TRAIL_SCHEMA_VERSIONING.md`](COGNITIVE_TRAIL_SCHEMA_VERSIONING.md).

## Good First Issues

### 1. Add PR-review diff fixtures

Goal: create a small fixture corpus for deterministic PR-review trail tests.

Suggested path:

```text
examples/pr_review_fixtures/
```

Acceptance criteria:

- Add at least four fixtures:
  - docs-only change;
  - code change without tests;
  - large diff with review-risk pressure;
  - risky shell-command or file-system change.
- Each fixture includes expected review signals.
- No fixture contains secrets, private code, tokens, or personal data.
- The fixture README explains what each case is testing.

Suggested labels: `good first issue`, `fixture`, `cooperative-precision`, `pr-review`

### 2. Add role-output fixtures

Goal: make attached role outputs more realistic and testable.

Suggested path:

```text
docs/examples/pr_role_outputs.*.json
```

Acceptance criteria:

- Add at least two role-output samples:
  - one clean cooperative review;
  - one noisy or unsupported review.
- Unknown actors must stay rejected by the parser.
- Outputs use only current LS actor roster unless the roster is explicitly updated.
- Documentation states whether outputs are sample artifacts or real actor outputs.

Suggested labels: `good first issue`, `fixtures`, `role-market`, `evidence`

### 3. Expand validator semantic checks

Goal: make invalid Cognitive Trail Runs fail before they become reviewer evidence.

Relevant file:

```text
scripts/validate_cognitive_trail_runs.py
```

Acceptance criteria:

- Add a failing test for each new semantic rule.
- Preserve current valid examples.
- Consider checking:
  - `needs_more_runs` is true when sample size is small;
  - `final_authority` or human operator appears when route reuse is recommended;
  - evidence references top role or top actor when contribution is claimed;
  - `decision` stays aligned with repeatability fields.
- Error messages identify the file and field path.

Suggested labels: `test`, `validator`, `contract`, `cooperative-precision`

### 4. Improve the generated Markdown report

Goal: make generated Cognitive Trail Run reports easier to paste into PR review comments and grant updates.

Relevant file:

```text
scripts/generate_pr_review_trail_run.py
```

Current implemented path:

```bash
python scripts/generate_pr_review_trail_run.py \
  --last 10 \
  --validate \
  --markdown-output reports/trails/pr_review_trail_run_report.md
```

Acceptance criteria for improvements:

- Add a compact mode for PR comments.
- Add a reviewer-summary section no longer than 10 lines.
- Keep the full route/evidence tables available.
- Preserve the non-claims section.
- Add tests for any new Markdown mode or section.

Suggested labels: `good first issue`, `reporting`, `benchmark`, `pr-review`

### 5. Improve CI artifact visibility

Goal: make CI-generated Cognitive Trail artifacts easier for reviewers to find and interpret.

Relevant workflow:

```text
.github/workflows/cognitive_trail_contract.yml
```

Current implemented artifact:

```text
cognitive-trail-report-${{ github.sha }}
```

Current artifact contents:

```text
reports/trails/ci/cognitive_trail_run.json
reports/trails/ci/cognitive_trail_run_report.md
```

Acceptance criteria for improvements:

- Add a workflow summary that links or names the uploaded artifact.
- Keep runtime JSON ignored by git.
- Keep the existing schema/semantic validation running.
- Consider uploading a compact PR-comment Markdown report when pull request context is available.
- Document any new artifact names in the quickstart.

Suggested labels: `ci`, `github-actions`, `artifact`, `cooperative-precision`

### 6. Promote one generated report into a curated example

Goal: define a safe process for turning runtime reports into checked-in examples.

Acceptance criteria:

- Add a short doc section explaining the promotion criteria.
- The promoted example must:
  - pass schema validation;
  - include clear non-claims;
  - avoid private data;
  - use stable task ids;
  - keep `needs_more_runs: true` unless evidence justifies otherwise.
- Add one additional curated example if a suitable runtime report exists.

Suggested labels: `docs`, `examples`, `curation`, `contract`

### 7. Add human-review outcome labels

Goal: connect Cognitive Trail results to human acceptance or rejection.

Acceptance criteria:

- Extend fixtures or examples with a safe, minimal human-review outcome signal.
- Do not write private reviewer identity.
- Outcome can distinguish:
  - accepted finding;
  - rejected finding;
  - needs follow-up;
  - false positive.
- Benchmark note explains how human outcomes would strengthen the result.
- If the schema changes, follow [`COGNITIVE_TRAIL_SCHEMA_VERSIONING.md`](COGNITIVE_TRAIL_SCHEMA_VERSIONING.md).

Suggested labels: `benchmark`, `human-review`, `evidence`, `safety`, `versioning`

## Medium Tasks

### 8. Add a small PR-review benchmark corpus

Goal: move from a tiny local sample toward a repeatable public benchmark.

Acceptance criteria:

- Add at least 10 safe fixtures.
- Include expected evidence signals for each fixture.
- Include a command that runs all fixtures.
- Produce a visible summary table.
- Keep scoring transparent and deterministic.

Suggested labels: `benchmark`, `fixtures`, `research`, `cooperative-precision`

### 9. Add role-ablation comparison

Goal: measure which roles actually improve the PR-review route.

Acceptance criteria:

- Compare full route against routes with one role removed.
- Report whether `risk_critic`, `evidence_verifier`, or `final_reviewer` changes lift.
- Keep route-level claims contextual.
- Add a short interpretation section.

Suggested labels: `benchmark`, `ablation`, `role-market`, `research`

### 10. Extend schema versioning with migration examples

Goal: keep Cognitive Trail schema evolution reviewer-safe as new fields are added.

Relevant file:

```text
docs/COGNITIVE_TRAIL_SCHEMA_VERSIONING.md
```

Current implemented baseline:

```text
cognitive_trail_run.v0.1 versioning policy
```

Acceptance criteria for improvements:

- Add a concrete `v0.1 -> v0.2` migration when a real schema change lands.
- Preserve at least one canonical example for each documented schema version.
- Update validator behavior for each supported schema version.
- Update quickstart, evidence snapshot, benchmark note, and contributor tasks when schema semantics change.

Suggested labels: `schema`, `docs`, `contract`, `versioning`

## Definition of Done

A strong PR should include:

- a small, focused change;
- updated docs when behavior changes;
- tests or validation commands;
- no private data;
- no global model-ranking claims;
- a short PR description explaining the evidence value.

## Maintainer Review Checklist

Before merging, check:

- Does this improve the reviewer-visible evidence chain?
- Does it preserve the non-claim boundary?
- Does it keep generated runtime JSON out of git?
- Does it pass `scripts/validate_cognitive_trail_runs.py`?
- Does it make the next similar contribution easier?
- If it changes schema semantics, does it follow `COGNITIVE_TRAIL_SCHEMA_VERSIONING.md`?

## One-Line Contributor Goal

```text
Make LS Cognitive Trails easier to validate, reproduce, and extend without overclaiming what the current benchmark proves.
```
