# Cognitive Trail Evidence Snapshot

Status: **working local research MVP**.

This is a compact reviewer snapshot for the LS Cognitive Trail PR-review path.
It is intended for grant reviewers, maintainers, and technical evaluators who
need one page that answers:

```text
What exists?
How can it be checked?
What evidence is generated?
What is not claimed?
```

## One-Line Claim

```text
LS can record, validate, summarize, and expose one local PR-review Cognitive Trail Run that measures whether a cooperative route improved a task signal over a direct baseline.
```

This is a narrow infrastructure claim, not a global model-quality claim.

## Evidence Chain

```text
Cognitive Trail Run contract
-> JSON Schema
-> checked-in examples
-> PR-review benchmark note
-> validator with semantic checks
-> PR-review trail generator
-> Markdown reviewer report
-> generator tests
-> GitHub Actions workflow
-> workflow summary
-> downloadable JSON/Markdown artifact
```

## Current Snapshot

Canonical checked-in sample:

```text
examples/trails/generated_pr_review_sample.json
```

Current local benchmark values recorded in the sample:

```text
analyzed:             3/3
errors:               0
baseline_reward:      0.5943
cooperative_reward:   0.7233
lift:                 +0.1290
positive_lift:        3/3
top_role:             risk_critic
top_actor:            gonka
repeatability:        should_repeat_route=true, needs_more_runs=true
```

Interpretation:

```text
On the current small local PR-review sample, the cooperative route produced a better measured review signal than the direct baseline.
```

## Main Files

| Evidence | File |
| --- | --- |
| Reviewer quickstart | [`COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md`](COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md) |
| Contract | [`COGNITIVE_TRAIL_RUN_CONTRACT.md`](COGNITIVE_TRAIL_RUN_CONTRACT.md) |
| Schema | [`../schemas/cognitive_trail_run.schema.json`](../schemas/cognitive_trail_run.schema.json) |
| Canonical generated sample | [`../examples/trails/generated_pr_review_sample.json`](../examples/trails/generated_pr_review_sample.json) |
| Benchmark interpretation | [`COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md`](COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md) |
| Validator | [`../scripts/validate_cognitive_trail_runs.py`](../scripts/validate_cognitive_trail_runs.py) |
| Generator | [`../scripts/generate_pr_review_trail_run.py`](../scripts/generate_pr_review_trail_run.py) |
| Generator tests | [`../python/tests/test_generate_pr_review_trail_run.py`](../python/tests/test_generate_pr_review_trail_run.py) |
| CI workflow | [`../.github/workflows/cognitive_trail_contract.yml`](../.github/workflows/cognitive_trail_contract.yml) |
| Contributor tasks | [`COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md`](COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) |

## Local Verification Commands

Install dependencies:

```bash
python -m pip install jsonschema pytest
```

Validate checked-in examples:

```bash
python scripts/validate_cognitive_trail_runs.py
```

Run generator tests:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_generate_pr_review_trail_run.py
```

Generate and validate a runtime JSON artifact:

```bash
python scripts/generate_pr_review_trail_run.py --last 10 --validate
```

Generate JSON plus a human-readable Markdown report:

```bash
python scripts/generate_pr_review_trail_run.py \
  --last 10 \
  --validate \
  --markdown-output reports/trails/pr_review_trail_run_report.md
```

## CI Evidence

Workflow:

```text
.github/workflows/cognitive_trail_contract.yml
```

The workflow performs four evidence-producing actions:

```text
validate checked-in examples
-> run generator tests
-> generate and validate a fresh runtime trail JSON
-> generate a Markdown reviewer report
```

It also writes a GitHub Actions workflow summary that names the command, artifact,
file paths, and interpretation boundary.

Downloadable workflow artifact:

```text
cognitive-trail-report-${{ github.sha }}
```

Files inside:

```text
reports/trails/ci/cognitive_trail_run.json
reports/trails/ci/cognitive_trail_run_report.md
```

## What the Validator Checks

The validator checks:

- valid JSON;
- Draft 2020-12 JSON Schema compliance;
- `schema_version == cognitive_trail_run.v0.1`;
- `lift == cooperative_reward - baseline_reward`;
- `positive_lift` matches the sign of `lift`;
- route steps are contiguous from `1`;
- `top_role` is present in the recorded route;
- `top_actor` is present in the recorded route;
- contribution summary agrees with result fields.

## What the Markdown Report Adds

The JSON artifact is canonical and machine-checkable.

The Markdown report adds a reviewer-facing surface:

```text
summary
-> result table
-> route table
-> evidence table
-> contribution summary
-> repeatability decision
-> non-claims
-> one-line interpretation
```

This makes the same evidence usable in a PR discussion, grant packet, or technical review.

## Non-Claims

This snapshot does not claim:

- global model ranking;
- global actor or human contributor ranking;
- that `risk_critic` is always the best role;
- that `gonka` is globally best;
- production-grade evaluation;
- statistical sufficiency;
- that LS already operates a global live Cognitive Trail Network;
- that any route may become action, memory, or reputation without human authority.

## Current Limitations

Current limitations:

- sample size is small;
- scoring is deterministic and heuristic;
- role outputs may be sample artifacts unless replaced by real actor outputs;
- CI/test outcomes are not yet part of the reward calculation;
- human review acceptance/rejection labels are not yet included;
- runtime reports are intentionally gitignored unless promoted into curated examples.

## What Would Strengthen the Evidence

The next strongest evidence improvements are:

1. A small public PR-review fixture corpus.
2. Real attached role outputs from configured actors or human reviewers.
3. Human-review outcome labels.
4. Role-ablation comparison.
5. CI/test outcome signals added to reward calculation.
6. More generated reports promoted into curated checked-in examples.

## Reviewer Bottom Line

```text
The current Cognitive Trail path is not a finished evaluation platform, but it is already an inspectable evidence loop: contract -> schema -> examples -> generator -> validator -> tests -> CI summary -> downloadable artifacts -> explicit non-claims.
```
