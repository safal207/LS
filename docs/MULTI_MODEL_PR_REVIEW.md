# LS Multi-Model PR Review V0.1

This CI lane turns the existing LS free PR-review route into an executable,
provider-neutral review runtime.

It is intentionally advisory by default:

```text
exact PR diff
-> independent model findings
-> deterministic validation
-> cross-model confirmation
-> human review evidence
```

A model never approves or merges a pull request.

## Why two workflows exist

The implementation separates candidate-code testing from external model access.

### `multi_model_review_contract.yml`

Runs on ordinary `pull_request` and `push` events with read-only permissions. It
checks the candidate implementation itself:

- Python compilation;
- deterministic unit tests;
- model-roster validation.

It has no provider credential.

### `multi_model_pr_review.yml`

Runs automatically only for pull requests targeting `main`, using
`pull_request_target`. It checks out the trusted default-branch implementation,
not the pull-request branch.

The workflow then obtains the PR diff through the GitHub API and treats it only
as untrusted data. It never executes code from the reviewed branch.

For stacked pull requests whose base is not `main`, run the trusted workflow
manually and provide the PR number.

## Initial model roster

The roster is stored in `.github/ai-review-models.json`.

| Role | Preferred free endpoint | Activation |
| --- | --- | --- |
| Fast diff reviewer | `cohere/north-mini-code:free` | Every review |
| Deep implementation reviewer | `poolside/laguna-m.1:free` | Every review |
| Independent challenger | `tencent/hy3:free` | Every review |
| Architecture/governance reviewer | `nvidia/nemotron-3-ultra-550b-a55b:free` | High-risk diffs |
| Evidence tie-breaker | `openai/gpt-oss-120b:free` | Conflicting evidence |

Each role has explicit free fallbacks. Before any call, the runtime reads the
provider model catalog and accepts an endpoint only when:

- the exact model id exists;
- prompt and completion prices are both zero;
- the endpoint has not passed its declared expiration date;
- the same resolved endpoint has not already filled another role in that run.

The runtime never silently removes `:free` or switches to a paid model.

## Repository setup

Add this Actions secret:

```text
OPENROUTER_API_KEY
```

The key identifies the OpenRouter account. The configured model endpoints are
free, but provider rate limits and availability still apply.

Optional repository variables:

```text
LS_AI_REVIEW_MODE=advisory
LS_ALLOW_EXTERNAL_AI_REVIEW=true
```

`LS_ALLOW_EXTERNAL_AI_REVIEW` is required only for private repositories. Public
repositories run automatically. Private repositories remain disabled unless a
maintainer explicitly opts in because their diff would leave GitHub.

## Policy modes

### Advisory — default

Provider failures, missing credentials, rate limits, and incomplete lanes are
reported as `PARTIAL`. The workflow publishes the evidence but does not become a
merge authority.

A confirmed high-severity issue produces an aggregate `REQUEST_CHANGES` verdict,
but the workflow remains advisory.

### Strict — opt in after calibration

Set:

```text
LS_AI_REVIEW_MODE=strict
```

Strict mode fails the final policy step when:

- the review is incomplete; or
- a critical/high finding is independently confirmed.

Do not make this check required until the free endpoints have been observed over
a representative set of LS pull requests.

## Exact-head binding

Every artifact contains:

- repository;
- pull-request number;
- base SHA;
- exact 40-character head SHA;
- SHA-256 digest of the original diff;
- selected model ids and fallbacks;
- model validation status;
- candidate and confirmed findings;
- policy outcome.

Immediately before publishing the PR comment, the workflow reads the current PR
head again. If it differs from the captured head, publication fails and stale
evidence is not posted.

## Finding lifecycle

```text
one model reports a problem
-> candidate finding

at least two independent roles report an overlapping problem
-> confirmed finding

confirmed critical/high finding
-> aggregate REQUEST_CHANGES
```

Overlap requires:

- the same exact changed file;
- compatible line locations when both provide a line;
- meaningful token overlap in the title and failure scenario.

A model response is rejected when it is not one JSON object, uses an unknown
verdict or severity, exceeds field limits, or points outside the changed files.

## Prompt-injection and data boundary

The model receives only:

- exact-head metadata;
- changed-file paths;
- deterministic risk tags;
- a bounded PR diff.

Before transmission, LS redacts common secret-shaped assignments, bearer tokens,
and private-key blocks. The diff is length-bounded and tagged as untrusted.

Models receive no GitHub token, tools, shell, repository checkout, or permission
to apply patches. Returned text is schema-validated and Markdown-sanitized before
publication.

This reduces risk; it does not make external transmission appropriate for every
private repository. Private use therefore requires explicit opt-in.

## Local contract test

```bash
python -m py_compile scripts/run_multi_model_pr_review.py
python -m unittest python/tests/test_multi_model_pr_review.py -v
```

## Local advisory run

Save a diff and provide exact SHAs:

```bash
git diff origin/main...HEAD > /tmp/ls-pr.diff

OPENROUTER_API_KEY=... \
python scripts/run_multi_model_pr_review.py \
  --diff-file /tmp/ls-pr.diff \
  --repository safal207/LS \
  --pr-number 123 \
  --base-sha 0000000000000000000000000000000000000000 \
  --head-sha 1111111111111111111111111111111111111111 \
  --mode advisory \
  --output artifacts/multi-model-review.json \
  --markdown-output artifacts/multi-model-review.md
```

Use real Git SHAs in an actual run.

## Bootstrap behavior

The secret-bearing workflow is trusted from the default branch. Therefore, the
pull request that first adds this workflow can run only the contract workflow.
After merge, synchronize an open PR or use `workflow_dispatch` to perform the
first live model review.

## Promotion path

V0.1 should collect evidence before becoming a required check:

1. run advisory reviews on ordinary and high-risk PRs;
2. measure invalid-output, rate-limit, and provider-unavailable rates;
3. compare candidate findings with CodeRabbit, Codex, tests, and human decisions;
4. tune overlap thresholds and role prompts;
5. enable strict mode only when false blocking is acceptably low;
6. make the check required only through an explicit governance decision.
