# Gonka Shadow Causal Review v0.1

## Purpose

This lane evaluates Gonka-hosted MiniMax on exact-head pull-request patches without granting the provider any repository authority.

The lane is experimental measurement evidence. It is not part of the trusted ensemble report and cannot approve, request changes, block, publish a PR comment, or merge.

## Trigger and trust boundary

Gonka runs only inside the protected `Trusted Causal Review — Label Command` workflow after a maintainer applies the `causal-review` label to a non-draft, same-repository pull request.

The workflow:

1. checks out the protected `main` implementation;
2. collects the pull-request patch as untrusted data through the GitHub API;
3. verifies the exact repository, PR, head SHA, branch, and patch digest before exposing credentials;
4. runs native reviewers blind and independently;
5. verifies the exact head again after model calls;
6. uploads the Gonka lane only as a seven-day evidence artifact.

No target-PR code is checked out, installed, sourced, built, or executed.

## Provider configuration

Default configuration:

- API endpoint: `https://api.gonkagate.com/v1/chat/completions`
- model: `minimaxai/minimax-m2.7`
- secret: `GONKA_BROKER_API_KEY`
- maximum output: `8000` tokens

Repository variables may override:

- `GONKA_ENABLED`
- `GONKA_API_URL`
- `GONKA_MODEL`
- `GONKA_MAX_TOKENS`

Setting `GONKA_ENABLED=false` produces an explicit `NOT_RUN` artifact and makes no model call.

## Evidence outputs

The protected workflow stores:

- `gonka-review.json` — validated `ls.causal-review.v0.1` artifact;
- `gonka-review.md` — human-readable rendering;
- `gonka-response.raw.json` — raw broker response or broker error body.

A completed lane requires the broker response to identify the requested model, allowing only case normalization or a provider snapshot suffix. Missing or mismatched model identity produces a diagnostic artifact with no findings.

## Shadow invariants

- The lane is omitted from `causal_review_pilot.py --raw` and `--reviews` inputs.
- A completed provider verdict is forced to `COMMENT` in the stored artifact.
- All findings remain `CANDIDATE` and require human adjudication.
- The lane cannot create or update PR comments.
- The lane cannot approve, block, or merge.
- Missing credentials, broker failures, malformed JSON, and model mismatch are explicit evidence states rather than silent success.
