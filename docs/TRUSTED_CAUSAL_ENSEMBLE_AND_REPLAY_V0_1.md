# LS Trusted Causal Ensemble and Historical Replay v0.1

## Goal

The first three causal pilots proved the exact collector and reporting pipeline, but all reviewer
lanes were incomplete. This slice moves model execution behind an automatic two-workflow trust
boundary and adds a separate exact-head replay protocol for already adjudicated historical
findings.

```text
pull_request event
  → unprivileged exact collector
  → immutable request artifact
  → workflow_run on trusted main
  → re-fetch and compare exact patch bytes
  → blind Grok and DeepSeek causal lanes
  → observer adapters
  → second exact-head verification
  → provisional ensemble report
```

## Workflow A — unprivileged collection

[`.github/workflows/causal-review-collect.yml`](../.github/workflows/causal-review-collect.yml)
runs on open, synchronized, reopened, or ready-for-review non-draft pull requests.

It receives no model secrets and explicitly checks out the repository default branch rather than
target-PR code. It collects:

- exact open PR head SHA;
- exact GitHub patch bytes and SHA-256;
- raw GitHub review-thread pages;
- CodeRabbit and Qodo source bundles;
- an unprivileged collection context.

The artifact is a request, not trusted evidence. Upload success does not authorize a model call.

## Workflow B — trusted ensemble

[`.github/workflows/trusted-causal-review-ensemble.yml`](../.github/workflows/trusted-causal-review-ensemble.yml)
runs only after a successful `Causal Review Collect` workflow.

`workflow_run` has a privileged token and may receive repository secrets, so it treats every
artifact byte as untrusted. Before any model call,
[`tools/causal_review_request.py`](../tools/causal_review_request.py):

1. validates the manifest schema and repository identity;
2. recomputes SHA-256 over the persisted patch bytes;
3. verifies both observer bundles target the same repository, PR, head, and digest;
4. rereads the PR from GitHub;
5. requires open and non-draft state;
6. requires the current head to equal the collected head;
7. re-fetches the current patch and requires byte-for-byte equality.

The same verification is repeated after model calls. A force-push during review prevents report
publication.

The trusted workflow never executes target-PR code, scripts, actions, binaries, or dependencies.
All executable tooling comes from the default branch.

## Native causal reviewers

### Grok

The existing Grok wrapper remains pinned to `grok-4.5` and requires `XAI_API_KEY`. Missing secret,
provider model mismatch, invalid output, partial patch coverage, and stale target are explicit
non-completed states.

### DeepSeek

[`tools/deepseek_causal_review.py`](../tools/deepseek_causal_review.py) calls the configured
DeepSeek chat-completions endpoint and requires:

- repository secret `DEEPSEEK_API_KEY`;
- requested model from repository variable `DEEPSEEK_MODEL`, default `deepseek-reasoner`;
- endpoint from repository variable `DEEPSEEK_API_URL`, default
  `https://api.deepseek.com/chat/completions`;
- exact requested/provider model equality;
- native schema-complete causal findings;
- at least one evidence item per finding.

Missing credentials produce `NOT_RUN`, never a zero-finding success. Invalid model output produces
`DIAGNOSTIC`, never a finding.

Grok and DeepSeek run blind: neither receives the other reviewer's result.

## Observer lanes

CodeRabbit and Qodo remain optional observer imports. Their absence is
`DIAGNOSTIC/UNVERIFIED`; it does not block native model execution and does not count as positive
evidence.

## Ensemble report

`tools/causal_review_pilot.py` now accepts native `ls.causal-review.v0.1` artifacts as raw causal
evidence in addition to CodeRabbit/Qodo bundles and the DeepSeek provider lane.

One report may contain at most one lane per reviewer. Raw item count, execution status,
provenance, exact target, and adapted finding count must match. The report remains:

```text
measurement_status: PROVISIONAL
production_claim_allowed: false
human_adjudication: PENDING
```

The ensemble cannot approve, block, or merge.

## Historical replay

Historical replay answers a different question: how much human queue compression would explicit
root-cause clustering have produced for already published and adjudicated findings?

It does not claim to rerun a model or reverify old code. Every record must preserve:

- source comment/review URL in the target repository;
- reviewer identity;
- exact reviewed commit SHA;
- human adjudication;
- explicit root-cause key for true findings.

Implementation and schema:

- [`tools/historical_causal_replay.py`](../tools/historical_causal_replay.py)
- [`schemas/historical-causal-replay-v0.1.schema.json`](../schemas/historical-causal-replay-v0.1.schema.json)

One replay accepts records from one exact PR head only. Cross-head records fail closed. Summary
reports add per-target counts but never merge root-cause clusters across PR heads.

Adjudication values:

```text
TRUE_CONFIRMED
TRUE_REPRODUCED
FALSE_POSITIVE
REQUIRES_HUMAN_DECISION
```

Metrics:

```text
causal_deduplication_rate =
  1 - root_cause_clusters / true_findings

human_queue_reduction =
  1 - (root_cause_clusters + pending_decisions) / raw_findings
```

A replay with no pending decisions is `MEASURED`, but `production_claim_allowed` remains false. A
product-level claim still requires representative target selection and published source evidence.

## Non-goals

This slice does not:

- execute untrusted PR code with secrets;
- treat artifact download as authorization;
- infer semantic dedupe across reviewers;
- count missing reviewers as zero findings;
- merge or approve pull requests;
- claim a production noise-reduction percentage from deterministic fixtures alone.
