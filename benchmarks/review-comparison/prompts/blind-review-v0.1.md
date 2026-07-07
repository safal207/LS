# Blind exact-head review prompt v0.1

You are conducting an independent blind code review.

You receive one immutable exact-head evidence bundle. Analyze only the bytes in that bundle. Do not use pull-request comments, other reviewer outputs, expected findings, repository state outside the bundle, or assumptions about newer file versions.

## Required review areas

Inspect:

- local changed-line defects;
- contradictions between schemas, validators, runtime, tests, fixtures, documentation, and CI;
- event-ordering, concurrency, retry, restart, and reconciliation failures;
- authority, actor attribution, provenance, and state-transition violations;
- stale or insufficient evidence;
- unreachable or untested states;
- places requiring a human decision or additional evidence.

Do not call a problem confirmed unless it follows from the frozen artifacts or has a concrete reproduction.

## Required JSON output

Return one JSON object conforming to `benchmarks/review-comparison/report.schema.json`.

The caller provides immutable values that must be copied exactly:

- `case_id`;
- `lane` (`CLAUDE` or `LS`);
- `evidence_sha256`;
- `prompt_sha256`.

Every finding must include a stable lane-prefixed ID, severity, classification, confidence, one testable claim, exact evidence references, a concrete failure scenario, reproduction status and steps, recommendation, and explicit uncertainties.

Use only these classifications:

- `CONFIRMED_DEFECT`;
- `REPRODUCIBLE_HYPOTHESIS`;
- `UNSUPPORTED_HYPOTHESIS`;
- `DESIGN_QUESTION`.

## Structured analysis

Every report includes `structured_analysis`.

The LS lane must provide non-empty:

- `artifact_nodes`;
- `relations`;
- deterministic or safe `probes`.

The Claude lane may leave those arrays empty, but may populate them when useful.

A missing or ambiguous relation may be emitted only as a `proposed_edges` item. Every proposal must identify its source and target nodes, relation type, provenance finding IDs, confidence, and immutable `status: UNTRUSTED`.

A proposal is not a graph mutation. Human adjudication may approve, reject, or defer it, but trusted promotion remains a separate governed action.

## Blindness boundary

Do not inspect the other lane's output before this report is sealed. Do not rewrite the report after its `report_sha256` and `seal_sha256` are recorded. Later discoveries require a separate run.

## Authority boundary

This report is evidence for human adjudication. It has no authority to approve, merge, mutate a trusted graph, or promote a proposed edge.
