# LS GitHub Collection and DeepSeek Causal Lane v0.1

## Purpose

Slice B2 separates two boundaries that must not be conflated:

1. collecting exact GitHub reviewer evidence;
2. adapting one wrapper-owned DeepSeek execution into the causal-review contract.

```text
GitHub exact PR head + patch bytes + review threads
  → raw collection manifest
  → CodeRabbit / Qodo bundles
  → provider adapters

DeepSeek wrapper execution + native causal findings
  → provenance/model validation
  → DeepSeek candidate artifact

validated artifacts for one exact target
  → root-cause clustering
  → human adjudication
```

## GitHub collector

Implementation:

- [`tools/github_causal_review_collector.py`](../tools/github_causal_review_collector.py)
- [`tests/test_github_causal_review_collector.py`](../tests/test_github_causal_review_collector.py)

Example:

```bash
GITHUB_TOKEN=... python tools/github_causal_review_collector.py \
  --repository safal207/LS \
  --pr-number 874 \
  --output-dir /tmp/causal-collection
```

The collector performs this sequence:

```text
read open, non-draft PR head
  → fetch exact patch bytes
  → fetch all review-thread pages
  → verify every collected thread has complete comment pagination
  → reread PR head
  → reject any head change
  → hash exact patch bytes
  → persist raw evidence and provider bundles
```

Outputs:

```text
collection-manifest.json
target.patch
github-review-threads.raw.json
coderabbit-bundle.json
qodo-bundle.json
```

### Evidence boundary

The collector groups a thread only when its root comment author is an expected provider identity:

- `coderabbitai` or `coderabbitai[bot]`;
- `qodo-code-review` or `qodo-code-review[bot]`.

Human-authored and unsupported-bot threads remain in the raw GraphQL pages but do not enter a
provider bundle.

A provider bundle with collected threads is `COMPLETED/MATCHED` only for the narrower claim that
those exact provider-authored threads were collected for the frozen target. It does **not** claim
full provider coverage or prove that silence means no findings.

When no provider-authored thread exists, the bundle is:

```text
status: DIAGNOSTIC
provenance: UNVERIFIED
findings after adaptation: none
```

This prevents `no thread found` from being interpreted as `provider completed with zero findings`.

### Fail-closed cases

Collection stops without a trusted manifest when:

- the PR is closed or draft;
- the head SHA changes during collection;
- the patch response is empty;
- a thread or comment page is incomplete;
- GraphQL returns errors;
- structural fields have invalid types;
- patch bytes or target metadata cannot be preserved exactly.

## DeepSeek native causal lane

Machine schema:

- [`schemas/deepseek-causal-lane-v0.1.schema.json`](../schemas/deepseek-causal-lane-v0.1.schema.json)

Implementation:

- [`tools/deepseek_causal_review_adapter.py`](../tools/deepseek_causal_review_adapter.py)
- [`tests/test_deepseek_causal_review_adapter.py`](../tests/test_deepseek_causal_review_adapter.py)

Example:

```bash
python tools/deepseek_causal_review_adapter.py \
  deepseek-lane.json \
  --output deepseek-review.json
```

The wrapper owns:

- exact repository, PR, head SHA, and patch digest;
- requested model identity;
- provider-returned model identity;
- execution status and provenance.

DeepSeek must supply each finding natively with:

```text
source id
severity and location
change
root cause
failure mechanism
observable effect
impact
evidence
confidence
reproduction or next experiment
recommendation
```

The adapter does not infer a missing root cause, invent evidence, or convert prose into a complete
causal chain.

### Execution semantics

`COMPLETED` requires:

- `provenance=MATCHED`;
- non-null provider model identity;
- exact requested/provider model equality;
- schema-complete native causal findings.

Every accepted DeepSeek finding becomes `CANDIDATE`; the review-level verdict is advisory
`COMMENT`.

`NOT_RUN`, `FAILED`, and `DIAGNOSTIC` must contain zero findings and produce no verdict. This makes
an unavailable DeepSeek credential or unexecuted lane visible rather than silently positive.

### Dedupe boundary

Default keys are provider-local:

```text
external.deepseek.<stable-hash>
```

A shared root-cause key requires an explicit human `dedupe_overrides` entry. Overrides may not use
the reserved `external.*` namespace.

## Reproducible demo versus production pilot

The deterministic tests demonstrate:

- exact patch/head binding;
- provider grouping;
- diagnostic silence handling;
- native DeepSeek causal validation;
- explicit `NOT_RUN` semantics;
- provider-local dedupe behavior.

These tests are a reproducible contract demonstration, not a production noise-reduction result.
A production pilot still requires collecting artifacts from the same three frozen targets defined
in issue #867, recording the resulting raw counts and clusters, and completing human adjudication.
