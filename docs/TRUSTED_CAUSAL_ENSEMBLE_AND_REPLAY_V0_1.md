# LS Trusted Causal Ensemble and Historical Replay v0.1

## Goal

The first causal pilots proved the exact collector and reporting pipeline, but reviewer execution
was unreliable when it depended on comments and a second `workflow_run` payload. The current design
uses separate trust paths for same-repository and fork pull requests.

```text
same-repository pull_request
  → trusted default-branch workflow and tooling
  → exact patch collection
  → PR number + head SHA + branch + patch-byte verification
  → blind Grok, DeepSeek, and Codex causal lanes
  → observer adapters
  → second exact-head verification
  → provisional ensemble report

fork pull_request
  → unprivileged exact collector
  → observer evidence artifact only
  → no repository model secrets
```

## Same-repository trusted workflow

[`.github/workflows/trusted-causal-review-same-repo.yml`](../.github/workflows/trusted-causal-review-same-repo.yml)
runs on open, synchronized, reopened, or ready-for-review non-draft pull requests targeting
`main` when the head repository equals the current repository.

The workflow explicitly checks out the repository default branch with persisted credentials
disabled. It never checks out the target PR head. Before reading model credentials it:

1. collects the current PR through GitHub API;
2. persists the exact patch bytes and SHA-256;
3. records CodeRabbit and Qodo source bundles;
4. requires the artifact PR number to equal the pull-request event number;
5. requires the artifact and current PR head to equal the event head SHA;
6. requires the current PR branch to equal the event head branch;
7. requires a same-repository head;
8. re-fetches the current patch and requires byte-for-byte equality.

Only after this verification does the workflow inspect `XAI_API_KEY`, `DEEPSEEK_API_KEY`, and
`OPENAI_API_KEY`. Missing credentials create explicit `NOT_RUN` artifacts.

The exact verification is repeated after all model calls. A force-push, branch move, closed PR,
draft transition, or patch change prevents report publication.

The workflow never executes, imports, installs, builds, or tests target-PR code while model secrets
are available. All executable review tooling comes from the default branch.

## Fork workflow

[`.github/workflows/causal-review-collect.yml`](../.github/workflows/causal-review-collect.yml)
runs only when the PR head repository differs from the current repository.

It receives read-only repository permissions and no model secrets. It collects exact patch and
observer evidence, records `secret_access=false` and
`native_reviewers=NOT_AUTHORIZED_FOR_FORK`, and uploads a seven-day artifact.

Fork evidence may later be inspected by a human, but it never automatically crosses into a
secret-backed native reviewer run.

## Removed workflow bridge

The previous `pull_request → artifact → workflow_run` bridge was removed. It was secure after
revalidation but operationally brittle because optional `workflow_run` PR metadata could be empty,
causing trusted review to skip before credential detection.

The direct same-repository workflow preserves the important security properties without requiring
cross-run target reconstruction:

- trusted default-branch code;
- same-repository authorization;
- event PR/head/branch binding;
- current GitHub API revalidation;
- persisted and freshly fetched patch-byte equality;
- pre-call and post-call verification.

## Native causal reviewers

### Grok

The Grok wrapper is pinned to `grok-4.5` and requires `XAI_API_KEY`. Missing secret, provider model
mismatch, invalid output, partial patch coverage, and stale target are explicit non-completed
states.

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

### Codex

[`tools/codex_causal_review.py`](../tools/codex_causal_review.py) uses the OpenAI Responses API and
requires repository secret `OPENAI_API_KEY`. Missing credentials produce `NOT_RUN`; provider quota
or rate errors remain explicit `FAILED` evidence. See
[`CODEX_CAUSAL_REVIEWER_V0_1.md`](CODEX_CAUSAL_REVIEWER_V0_1.md).

Grok, DeepSeek, and Codex run blind: no native reviewer receives another reviewer's result.

## Observer lanes

CodeRabbit and Qodo remain optional observer imports. Their absence is
`DIAGNOSTIC/UNVERIFIED`; it does not block native model execution and does not count as positive
evidence.

## Ensemble report

`tools/causal_review_pilot.py` accepts native `ls.causal-review.v0.1` artifacts as raw causal
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

This design does not:

- execute untrusted PR code with secrets;
- grant native model secrets to fork PRs;
- trust an artifact without current GitHub API revalidation;
- infer semantic dedupe across reviewers;
- count missing reviewers as zero findings;
- merge or approve pull requests;
- claim a production noise-reduction percentage from deterministic fixtures alone.
