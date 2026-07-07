# Blind review benchmark v0.1

## Purpose

This protocol compares a frontier-model review lane with the LS Living Evidence Graph lane without claiming that either lane is intrinsically more intelligent.

The tested hypothesis is:

> Review reliability depends on evidence identity, structural context, reproducibility, adjudication, and authority boundaries in addition to model capability.

The benchmark distinguishes useful hypothesis generation from proven engineering findings.

## Roles

- **CLAUDE lane**: frontier-model blind review.
- **LS lane**: graph/probe blind review.
- **Human adjudicator**: final authority over truth, severity, clustering, and edge-proposal decisions.

Neither review lane may approve, merge, or mutate trusted graph state.

## Frozen input

Both lanes receive the same exact-head evidence bundle identified by repository, PR number, base and head commit SHAs, exact file set, Git blob SHAs, content SHA-256 values, and one unified `evidence_sha256`.

A case remains `PREPARED` until acquisition succeeds and the unified digest is copied into the case. Only then may it become `FROZEN`.

Successful acquisition proves input identity. It does not prove that either lane found a defect.

## Blindness rules

Before sealing, neither lane may receive:

- the other lane's report;
- pull-request review comments;
- expected findings;
- human adjudication;
- repository state outside the frozen bundle.

The prompt is shared from `benchmarks/review-comparison/prompts/blind-review-v0.1.md`; its SHA-256 is recorded in both reports.

## Common report contract

Both reports conform to `benchmarks/review-comparison/report.schema.json`.

A finding is a testable claim. It includes exact evidence, a failure scenario, reproduction status, recommendation, confidence, and uncertainties.

The report classifications are:

- `CONFIRMED_DEFECT`;
- `REPRODUCIBLE_HYPOTHESIS`;
- `UNSUPPORTED_HYPOTHESIS`;
- `DESIGN_QUESTION`.

The LS lane must additionally provide non-empty structured artifact nodes, relations, and probes. This makes Lane B's graph/probe contribution inspectable instead of hiding it in prose.

## Proposed graph edges

Missing or ambiguous relations are emitted as `proposed_edges` with:

- source and target nodes;
- relation type;
- provenance finding IDs;
- confidence;
- immutable `UNTRUSTED` status.

Every proposal must receive exactly one human edge decision: approve proposal, reject proposal, or defer. Even approval does not mutate the trusted graph; promotion is a separate governed action. The scorecard therefore always reports `trusted_graph_mutations = 0`.

## Sealing

Each report is sealed before either output is revealed:

```bash
python tools/review_benchmark.py seal \
  --case benchmarks/review-comparison/cases/pr796-final-v0.1.json \
  --report artifacts/claude-report.json \
  --output artifacts/claude-seal.json
```

The seal binds:

- schema version;
- case and lane;
- evidence digest;
- prompt digest;
- reviewer identity;
- canonical report SHA-256;
- exact finding IDs and count;
- exact proposed-edge IDs and count.

`validate_seal()` verifies both cryptographic integrity and every semantic binding. An internally consistent but mismatched seal is rejected. Editing a sealed report invalidates it.

## Human adjudication

After both seals exist, a human may reveal the reports and build semantic clusters conforming to `benchmarks/review-comparison/adjudication.schema.json`.

Each source finding appears in exactly one cluster. This prevents silent omission and transitive over-merging.

Allowed truth decisions:

- `TRUE_REPRODUCED`;
- `TRUE_STATICALLY_PROVEN`;
- `PLAUSIBLE_NOT_PROVEN`;
- `FALSE_POSITIVE`;
- `DUPLICATE`;
- `OUT_OF_SCOPE`;
- `REQUIRES_HUMAN_DECISION`.

The adjudicator records whether attribution was correct, assigns severity, and decides every proposed edge.

## Ground truth and recall

Real PRs rarely have complete ground truth. The adjudication therefore declares `ground_truth_complete`.

- When false, recall is reported as `null`.
- When true, `known_truth` lists the complete seeded or independently established truth set and links each item to matching clusters.

This prevents pretending that recall is measurable on an open-ended real-world PR.

## Lane C complement/conflict analysis

The scorecard emits one category per adjudicated cluster:

- `BOTH_TRUE`;
- `CLAUDE_ONLY_TRUE`;
- `LS_ONLY_TRUE`;
- `FALSE_POSITIVE`;
- `EVIDENCE_GAP`;
- `DUPLICATE_FINDING`;
- `HUMAN_DECISION_REQUIRED`;
- `OUT_OF_SCOPE`.

This preserves per-result complement/conflict analysis instead of exposing only aggregate counts.

## Scorecard

```bash
python tools/review_benchmark.py score \
  --case benchmarks/review-comparison/cases/pr796-final-v0.1.json \
  --claude-report artifacts/claude-report.json \
  --claude-seal artifacts/claude-seal.json \
  --ls-report artifacts/ls-report.json \
  --ls-seal artifacts/ls-seal.json \
  --adjudication artifacts/adjudication.json \
  --output artifacts/scorecard.json
```

Per lane, v0.1 reports:

- total findings;
- true findings;
- false positives;
- precision;
- recall when ground truth is complete;
- reproduction rate among true findings;
- escalation quality;
- attribution accuracy;
- severity accuracy;
- unique true findings;
- plausible, out-of-scope, and human-required counts.

The scorecard also reports true overlap, cluster categories, edge-proposal decisions, and a canonical `scorecard_sha256`.

### Metric meanings

- **Precision**: adjudicated true findings divided by true plus false-positive findings.
- **Recall**: complete known-truth items detected by the lane divided by the complete known-truth count.
- **Reproduction rate**: true findings whose source report marked reproduction as `REPRODUCED` or `STATICALLY_PROVEN`.
- **Escalation quality**: findings explicitly classified as `DESIGN_QUESTION` or `UNSUPPORTED_HYPOTHESIS` that adjudication confirms should remain unproven or human-decided.
- **Attribution accuracy**: findings whose cited location was adjudicated correct.
- **Severity accuracy**: true findings whose reported severity matches adjudicated severity.

## Interpretation

Do not rank lanes by raw finding count.

A strong result may show Claude contributing unique high-value hypotheses while LS contributes exact-head identity, structural contradictions, reproducibility, safe stopping, and lower noise.

The intended product claim is:

> LS turns independent expert reasoning into exact, reproducible, governed engineering evidence.

## First case

`pr796-final-v0.1` uses final PR #796 coordinates:

```text
base: 66353d32cafe9a7e2e4b62ee98575859eca9f531
head: c482e19d829c39bdffa1352e8579c2362e7699c4
files: 19
```

The case remains `PREPARED` until the final exact-head acquisition artifact is verified and its unified digest is recorded.

## Follow-up case set

One real PR cannot establish recall. A credible published benchmark adds:

1. a real-world PR;
2. a seeded-defect PR with complete hidden ground truth;
3. a clean negative-control PR;
4. a stale-head mutation scenario.
