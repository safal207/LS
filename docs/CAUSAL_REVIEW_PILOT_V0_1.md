# LS Causal Review Pilot v0.1

## Purpose

The pilot combines raw reviewer evidence and adapted causal artifacts for one exact frozen pull
request. It reports the size of the provisional human adjudication queue without treating missing
reviewer executions as success.

```text
exact GitHub collection
  → CodeRabbit raw bundle + causal review
  → Qodo raw bundle + causal review
  → explicit DeepSeek lane + causal review
  → exact-target cluster validation
  → provisional pilot report
  → human adjudication pending
```

Implementation:

- [`tools/causal_review_pilot.py`](../tools/causal_review_pilot.py)
- [`tests/test_causal_review_pilot.py`](../tests/test_causal_review_pilot.py)
- [`.github/workflows/causal-review-pilot.yml`](../.github/workflows/causal-review-pilot.yml)

## Trusted command

A repository owner, member, or collaborator can post this native GitHub comment on an open,
non-draft pull request:

```text
/causal-review-pilot
```

The workflow is loaded from the default branch and explicitly checks out the default branch with
persisted credentials disabled. It never checks out or executes target-PR code.

The workflow:

1. freezes the exact target head and patch;
2. collects and persists raw GitHub review-thread evidence;
3. adapts CodeRabbit and Qodo bundles;
4. records an explicit DeepSeek `NOT_RUN` lane because the collector workflow has no DeepSeek
   credential;
5. builds a provisional multi-provider report;
6. uploads every raw and derived artifact;
7. upserts a run-linked PR comment.

## Artifact set

```text
target.patch
collection-manifest.json
github-review-threads.raw.json
coderabbit-bundle.json
coderabbit-review.json
qodo-bundle.json
qodo-review.json
deepseek-lane.json
deepseek-review.json
pilot-report.json
```

## Raw-to-review binding

Every raw artifact must match its adapted review on:

- reviewer/provider identity;
- repository;
- PR number;
- exact head SHA;
- patch SHA-256;
- execution status;
- provenance status.

A mismatch fails the report. Different exact targets cannot share a pilot.

## Metrics

The report records:

```text
raw_finding_count
evidence_bound_count
root_cause_cluster_count
corroborated_cluster_count
incomplete_review_count
adjudication_item_count
```

Derived metrics:

```text
contract_rejection_rate =
  1 - evidence_bound_count / raw_finding_count

causal_deduplication_rate =
  1 - root_cause_cluster_count / evidence_bound_count

human_queue_reduction =
  1 - adjudication_item_count / raw_finding_count
```

When a denominator is zero, the metric is `null`, not zero.

## Incomplete lanes count as work

Each `NOT_RUN`, `FAILED`, or `DIAGNOSTIC` reviewer lane adds one human adjudication item because a
human must decide whether to rerun, ignore, or replace the missing evidence.

Example:

```text
raw findings:              1
root-cause clusters:       1
incomplete lanes:          2
human adjudication items:  3
human queue reduction:   -200%
```

A negative value is intentional. It means incomplete evidence created more human work than the raw
finding count alone reveals. LS must not hide this debt by reporting silence as noise reduction.

## Provisional authority

Every v0.1 report contains:

```text
measurement_status: PROVISIONAL
production_claim_allowed: false
human_adjudication: PENDING
```

The workflow cannot approve, block, or merge a pull request. A provisional metric is not a product
claim and must not be presented as measured production improvement.

## Moving to a measured result

Issue #867 requires three frozen-target pilots:

1. low-risk dependency or documentation change;
2. known-defect security/workflow change;
3. product-facing change with previously adjudicated findings.

For each target, retain the full artifact set and complete human adjudication. Only then can LS
publish a cross-pilot queue-reduction result with supporting evidence.
