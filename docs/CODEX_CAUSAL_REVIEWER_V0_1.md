# LS Codex Causal Reviewer v0.1

## Purpose

Codex is the third native reviewer in the trusted causal ensemble. It runs independently from
Grok and DeepSeek against the same frozen patch and returns the same
`ls.causal-review.v0.1` contract.

```text
verified exact patch
  → OpenAI Responses API
  → model/provenance validation
  → causal contract validation
  → Codex candidate findings
  → exact-target ensemble clustering
```

Implementation:

- [`tools/codex_causal_review.py`](../tools/codex_causal_review.py)
- [`tests/test_codex_causal_review.py`](../tests/test_codex_causal_review.py)
- [`.github/workflows/trusted-causal-review-ensemble.yml`](../.github/workflows/trusted-causal-review-ensemble.yml)

## Configuration

Required repository secret:

```text
OPENAI_API_KEY
```

Optional repository variables:

```text
CODEX_MODEL                default: gpt-5.6-terra
CODEX_MAX_OUTPUT_TOKENS    default: 12000
OPENAI_RESPONSES_API_URL   default: https://api.openai.com/v1/responses
```

`gpt-5.6-terra` is the cost-balanced default. A repository owner may set `CODEX_MODEL` to another
Responses API model, such as `gpt-5.6-sol`, without changing trusted workflow code.

## Trust boundary

Codex runs only after `tools/causal_review_request.py` has:

- bound the artifact to the PR carried by `workflow_run`;
- rejected fork PRs by default;
- checked open and non-draft state;
- matched exact head SHA;
- recomputed the persisted patch SHA-256;
- re-fetched the current patch and required byte-for-byte equality.

The runner checks only default-branch tooling and the frozen patch data. It does not check out,
execute, import, install, or test target-PR code while `OPENAI_API_KEY` is available.

The exact-head verifier runs again after all native model calls. A force-push prevents ensemble
report publication.

## Execution states

| Condition | Status | Provenance | Findings |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` missing | `NOT_RUN` | `UNVERIFIED` | none |
| HTTP error, including exhausted quota | `FAILED` | `UNVERIFIED` | none |
| response omits model identity | `DIAGNOSTIC` | `MISSING` | none |
| unexpected model identity | `DIAGNOSTIC` | `MISMATCH` | none |
| invalid JSON or causal contract | `DIAGNOSTIC` | `MATCHED` after model match | none |
| valid completed response | `COMPLETED` | `MATCHED` | candidates |

HTTP error details preserve the response status and provider error `code` and `type`. Therefore an
`insufficient_quota` response remains visible and cannot be confused with a successful zero-finding
review.

## Model provenance

The runner accepts either:

- exact requested model identity; or
- a dated provider snapshot whose name starts with the requested model plus `-`.

This preserves the requested family while recording the exact provider-returned model in the
review artifact.

## Usage evidence

A completed Codex artifact records available input, output, and total token counts in
`execution.details`. The raw Responses API object is retained in the workflow artifact.

Usage evidence is diagnostic; it does not grant authority to approve, block, or merge.

## Independence and authority

Codex receives:

- the shared causal-review instructions;
- wrapper-owned exact target metadata;
- the frozen untrusted patch.

It does not receive Grok, DeepSeek, CodeRabbit, or Qodo results before producing its artifact.
Every finding remains `CANDIDATE`; human adjudication is required. Codex cannot approve or merge a
pull request.
