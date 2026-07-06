# LS Multi-Model PR Review V0.1

This CI lane turns the existing LS free PR-review route into an executable,
provider-neutral review runtime.

```text
exact PR diff
-> bounded and redacted evidence packet
-> independent role-based reviews
-> deterministic output validation
-> candidate / confirmed findings
-> exact-head publication check
-> human review evidence
```

The lane is advisory by default. A model cannot approve or merge a pull request.

## Why two workflows exist

### `multi_model_review_contract.yml`

Runs on ordinary `pull_request` and `push` events with read-only repository
permissions. It validates candidate code through:

- Python compilation;
- deterministic unit tests;
- checked-in model-roster validation;
- an uploaded test-log artifact, including failed runs.

This workflow has no external-model credential.

### `multi_model_pr_review.yml`

Runs automatically only for pull requests targeting `main`, using
`pull_request_target`. It checks out the trusted default-branch implementation,
not the pull-request branch.

The workflow obtains the candidate diff through the GitHub API and treats it as
untrusted data. It never checks out or executes code from the reviewed branch.
For a stacked pull request whose base is not `main`, run the trusted workflow
manually and provide the open PR number.

## Initial model roster

The versioned roster lives in `.github/ai-review-models.json`.

| Role | Preferred zero-priced endpoint | Activation |
| --- | --- | --- |
| Fast diff reviewer | `cohere/north-mini-code:free` | Every review |
| Deep implementation reviewer | `poolside/laguna-xs-2.1:free` | Every review |
| Independent challenger | `tencent/hy3:free` | Every review |
| Architecture/governance reviewer | `nvidia/nemotron-3-ultra-550b-a55b:free` | High-risk diffs |
| Evidence tie-breaker | `openai/gpt-oss-120b:free` | Conflicting evidence |

Each role has explicit free fallbacks. Before a call, the runtime reads the
provider catalog and accepts an endpoint only when:

- the exact model id exists;
- prompt and completion prices are numerically zero;
- the endpoint has not passed its declared expiration date;
- the resolved endpoint has not already filled another independent role.

A `:free` suffix is not trusted by itself. The runtime never removes that suffix
or silently switches to an endpoint whose live catalog price is nonzero.

## Repository setup

Add this Actions secret:

```text
OPENROUTER_API_KEY
```

The configured endpoints are free, but rate limits and availability still apply.

Optional repository variables:

```text
LS_AI_REVIEW_MODE=advisory
LS_ALLOW_EXTERNAL_AI_REVIEW=true
```

`LS_ALLOW_EXTERNAL_AI_REVIEW` is required only for private repositories. Public
repositories run automatically. Private repositories remain disabled until a
maintainer explicitly allows their diff to leave GitHub.

## Policy modes

### Advisory — default

Provider failures, missing credentials, rate limits, incomplete model lanes, and
incomplete diff coverage are reported as `PARTIAL`. Evidence is published, but
the workflow does not become a merge authority.

An independently confirmed high-severity issue produces aggregate
`REQUEST_CHANGES`, while enforcement remains advisory.

### Strict — opt in after calibration

Set:

```text
LS_AI_REVIEW_MODE=strict
```

Strict mode fails the final policy step when:

- the review is incomplete; or
- a critical/high finding is independently confirmed.

Do not make this check required until free-endpoint availability and false-block
rates have been measured across representative LS pull requests.

## Exact-head and coverage binding

Every JSON artifact contains:

- repository and pull-request number;
- base SHA and exact 40-character head SHA;
- SHA-256 digest of the original diff;
- all changed files;
- files actually represented in the bounded evidence packet;
- omitted files and a truncation flag;
- selected model ids and fallbacks;
- candidate and confirmed findings;
- policy outcome.

If the diff exceeds the configured bound, the runtime still reviews the bounded
portion but marks the run `PARTIAL`. A finding may reference only a file actually
represented in that bounded packet; it cannot claim evidence from an omitted
file.

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

- the same exact reviewed file;
- compatible line locations when both provide a line;
- meaningful token overlap in the title and failure scenario.

A response is rejected when it is not one JSON object, uses an unknown verdict
or severity, exceeds field limits, or points outside the reviewed files.

## Prompt-injection and data boundary

The model receives only:

- exact-head metadata;
- reviewed-file paths;
- deterministic risk tags;
- a bounded PR diff.

Before transmission, LS redacts common credential-shaped assignments, bearer
values, and PEM key blocks. The packet is length-bounded and explicitly tagged
as untrusted.

Models receive no GitHub token, tools, shell, repository checkout, or permission
to apply patches. Returned text is schema-validated, whitespace-normalized, and
Markdown-neutralized before publication.

This reduces risk; it does not make external transmission appropriate for every
private repository. Private use therefore requires explicit opt-in.

## Local contract test

```bash
python -m py_compile scripts/run_multi_model_pr_review.py scripts/multi_model_review/*.py
python -m unittest python/tests/test_multi_model_pr_review.py -v
```

## Local advisory run

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

The external-call workflow is trusted from the default branch. Therefore, the
pull request that first adds this workflow runs only the contract lane. After
merge, synchronize another open PR or use `workflow_dispatch` for the first live
model review.

## Promotion path

1. Run advisory reviews on ordinary and high-risk PRs.
2. Measure invalid-output, rate-limit, provider-unavailable, and truncation rates.
3. Compare findings with CodeRabbit, Codex, tests, and human decisions.
4. Tune overlap thresholds, input bounds, and role prompts.
5. Enable strict mode only when false blocking is acceptably low.
6. Make the check required only through an explicit governance decision.
