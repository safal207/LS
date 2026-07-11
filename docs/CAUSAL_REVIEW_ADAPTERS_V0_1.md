# LS External Causal Review Adapters v0.1

## Purpose

External reviewer apps such as CodeRabbit and Qodo usually publish prose comments rather than the
native `ls.causal-review.v0.1` JSON envelope. The adapter layer converts their review threads into
contract-valid **candidate** artifacts while preserving the external evidence and refusing to
invent cross-provider agreement.

```text
raw provider thread bundle
  → author/provenance check
  → provider-specific parsing
  → evidence-bound candidate finding
  → contract validation
  → provider-local clustering
  → explicit human root-cause override
  → optional cross-provider corroboration
```

Implementation:

- [`tools/causal_review_adapters.py`](../tools/causal_review_adapters.py)
- [`tests/test_causal_review_adapters.py`](../tests/test_causal_review_adapters.py)

## Supported providers

v0.1 supports:

- CodeRabbit inline review threads authored by `coderabbitai` or `coderabbitai[bot]`;
- Qodo inline review threads authored by `qodo-code-review` or
  `qodo-code-review[bot]`.

Unexpected authors fail closed. A `COMPLETED` bundle requires matched provenance. `NOT_RUN`,
`FAILED`, and `DIAGNOSTIC` bundles remain verdict-less and finding-less under the base contract.

## Input bundle

Each adapter input is one JSON object:

```json
{
  "provider": "qodo",
  "target": {
    "repository": "safal207/LS",
    "pr_number": 866,
    "head_sha": "<40 lowercase hex>",
    "patch_sha256": "sha256:<64 lowercase hex>"
  },
  "execution": {
    "status": "COMPLETED",
    "provenance": "MATCHED",
    "details": "The provider author and frozen target were verified."
  },
  "threads": [
    {
      "id": "provider-thread-id",
      "author": {"login": "qodo-code-review"},
      "path": "tools/example.py",
      "line": 42,
      "is_resolved": false,
      "is_outdated": false,
      "source_url": "https://github.com/...",
      "body": "Raw provider review body"
    }
  ],
  "dedupe_overrides": {}
}
```

The raw bundle is the source artifact and must be retained separately. The causal artifact stores a
bounded excerpt and a stable source reference; it is not a replacement for the original provider
output.

## Conservative causal mapping

External prose is not treated as reproduced truth. Every active thread becomes:

- `claim_status=CANDIDATE`;
- `verdict=COMMENT` at the review level;
- an evidence reference to the provider thread;
- the provider wording preserved as the root-cause claim;
- an explicit note that the adapter has not independently reproduced the claim;
- a human decision point for impact and causal identity.

Resolved or outdated threads remain present in the raw bundle but are excluded from the active
causal queue.

## No semantic auto-deduplication

The adapter never concludes that two differently worded findings have the same root cause merely
because their symptoms look similar.

Without an override, keys are provider-local:

```text
external.qodo.<stable-hash>
external.coderabbit.<stable-hash>
```

Therefore similar Qodo and CodeRabbit findings remain separate `SINGLE_REVIEWER` clusters.

A cross-provider cluster is allowed only after an explicit adjudication override:

```json
{
  "dedupe_overrides": {
    "provider-thread-id": "prompt.patch-framing-boundary"
  }
}
```

When two independent artifacts on the same exact target use the same reviewed override, the base
clusterer may mark the root cause `CORROBORATED`. The override is evidence of a human mapping, not
proof that the finding is true.

## Noise report

The adapter CLI can build a deterministic report from raw bundles and their adapted reviews:

```bash
python tools/causal_review_adapters.py adapt qodo.json --output qodo-review.json
python tools/causal_review_adapters.py adapt coderabbit.json --output coderabbit-review.json
python tools/causal_review_adapters.py report \
  qodo.json coderabbit.json \
  --reviews qodo-review.json coderabbit-review.json \
  --output noise-report.json
```

The report records:

- raw thread count;
- ignored resolved/outdated thread count;
- evidence-bound finding count;
- exact root-cause cluster count;
- corroborated cluster count;
- incomplete reviewer lanes;
- provider-local and explicit override counts;
- contract rejection rate;
- causal deduplication rate;
- human queue reduction.

The report only accepts reviews for one exact repository, PR, head SHA, and patch digest. Different
targets cannot corroborate each other.

## Current boundary

v0.1 adapts provider comments already available from GitHub. It does not yet fetch GitHub threads,
create the raw bundles automatically, adapt DeepSeek output, or decide dedupe overrides. Those are
separate execution and adjudication slices under issue #867.
