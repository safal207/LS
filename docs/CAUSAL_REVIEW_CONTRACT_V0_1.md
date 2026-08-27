# LS Causal Review Contract v0.1

## Purpose

LS reviewer lanes currently produce useful but mostly flat findings. Flat lists create three
types of noise:

1. several agents describe the same root cause as different symptoms;
2. a confident sentence can look equivalent to reproduced evidence;
3. green workflow status can hide a reviewer lane that did not execute.

The causal review contract makes every reviewer produce an independent, evidence-bound graph
before LS clusters or adjudicates findings.

```text
frozen exact head
  → independent reviewer graph
  → contract validation
  → root-cause clustering
  → contradiction and evidence checks
  → human adjudication
  → bounded verdict
```

## Contract boundary

The machine-readable schema is
[`schemas/causal-review-v0.1.schema.json`](../schemas/causal-review-v0.1.schema.json).
The deterministic validator, renderer, and clusterer are implemented in
[`tools/causal_review.py`](../tools/causal_review.py).

The wrapper owns facts a model must not invent:

- reviewer identity;
- requested and provider model identity;
- target repository and PR number;
- exact head SHA;
- patch SHA-256;
- execution and provenance status.

The reviewer supplies:

- verdict and risk level;
- evidence-bound findings;
- a full causal chain for every finding;
- tests aimed at causal links and violated invariants;
- explicit human decision points.

## Required causal chain

Each finding traces:

```text
change
  → root cause
  → failure mechanism
  → observable effect
  → impact
```

A symptom without a supported root cause is rejected by the contract. A recommendation without
evidence is rejected. A non-executed or provenance-mismatched lane cannot publish a verdict or
findings.

## Independent review rule

Reviewer agents must run blind. They may share:

- the same frozen target;
- the same contract and severity vocabulary;
- the same repository requirements.

They must not see another reviewer's findings before producing their own causal artifact. This
prevents anchoring and false consensus.

## Trusted execution boundary

The model-backed Grok lane is invoked only through a trusted `/grok-causal-review` issue comment.
GitHub loads `issue_comment` workflows from the repository default branch, and the workflow checks
out that default branch explicitly with persisted Git credentials disabled.

The target PR contributes only untrusted diff bytes fetched through the GitHub API. The workflow
does not execute reviewer scripts, actions, or other code from the target PR while `XAI_API_KEY` is
available. Contract tests may run on ordinary `pull_request` events because they receive no model
secret.

## Exact patch boundary

Before a model call, the runner recomputes the SHA-256 of the patch bytes and compares it with the
wrapper-owned `target.patch_sha256`. A mismatch fails closed.

The patch is transported inside a JSON data envelope rather than a Markdown fence. Triple
backticks or instruction-like strings inside the diff remain data and cannot terminate the wrapper
framing.

The causal lane must not publish a `COMPLETED` verdict for partial patch coverage. When the patch
exceeds the configured context/cost boundary, the runner emits `DIAGNOSTIC` with no verdict and no
findings. Future chunking must bind every chunk and an aggregate coverage manifest to the same
exact target before a complete verdict is allowed.

## Root-cause clustering

LS clusters only findings with the same explicit `dedupe_key`. The key represents the root cause
plus the violated invariant, not the symptom.

Examples:

```text
ci.force-push.exact-head-binding
api.retry.idempotency-boundary
auth.role-check.missing-server-enforcement
```

One clustering batch must share the same:

- repository;
- PR number;
- exact head SHA;
- patch SHA-256.

This prevents similarly named root causes from different commits or repositories from becoming
false corroboration.

Consequences:

- one cause with four symptoms becomes one cluster;
- one symptom caused by two different defects remains two clusters;
- two independent reviewers supporting one key become `CORROBORATED`;
- a single-reviewer cluster remains `SINGLE_REVIEWER`;
- rejected findings do not contribute support.

Corroboration is not automatic truth. Human adjudication still decides whether evidence proves
the causal links.

## Execution semantics

| Execution status | Verdict allowed | Findings allowed |
| --- | --- | --- |
| `COMPLETED` with `MATCHED` provenance | yes | yes |
| `NOT_RUN` | no | no |
| `FAILED` | no | no |
| `DIAGNOSTIC` | no | no |

This preserves the LS v0.1 rule that green orchestration cannot launder an unexecuted reviewer,
partial patch, or invalid provenance lane into positive evidence.

A final head mismatch discards only a previously completed model result. Existing `NOT_RUN`,
`FAILED`, or `DIAGNOSTIC` status is preserved and is never upgraded to matched provenance.

## Measuring noise

For a pilot containing independent reviewer artifacts:

```text
raw_finding_count = total findings emitted by completed reviewers
evidence_bound_count = findings accepted by the contract
root_cause_cluster_count = unique accepted dedupe keys
corroborated_cluster_count = clusters supported by at least two reviewers
```

Recommended metrics:

```text
contract_rejection_rate =
  1 - evidence_bound_count / raw_finding_count

causal_deduplication_rate =
  1 - root_cause_cluster_count / evidence_bound_count

human_queue_reduction =
  1 - adjudication_items / raw_finding_count
```

Do not claim a fixed percentage before a measured A/B pilot. Compare the existing flat review
and causal review on the same frozen PR heads.

## Rollout

### Slice A — contract and Grok causal pilot

- deterministic schema, validator, renderer, and clusterer;
- independent Grok causal lane;
- trusted default-branch execution through `/grok-causal-review`;
- exact-head and exact-patch binding;
- fail-closed behavior for partial patch coverage;
- separate artifact and comment marker, so flat and causal outputs can be compared.

### Slice B — external reviewer adapters

Normalize CodeRabbit, Qodo, DeepSeek, and other reviewer outputs into separate causal artifacts.
Adapters must preserve raw evidence and must not infer agreement merely from similar wording.

### Slice C — multi-review aggregation

Aggregate validated artifacts, measure noise reduction, identify contradictions, and send only
root-cause clusters to human adjudication.

## Non-goals

v0.1 of this contract does not:

- replace human adjudication;
- assume two agreeing models are correct;
- auto-merge PRs;
- modify OpenRouter, Responses API, or model selection;
- change the existing flat Grok lane before the A/B pilot is measured.
