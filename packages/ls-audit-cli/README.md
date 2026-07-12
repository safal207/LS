# LS Exact-Head Audit CLI

A standard-library-only operator CLI that freezes bounded GitHub.com evidence for one pull request at one exact 40-character head SHA.

## Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install ./packages/ls-audit-cli
```

This package does not install the legacy GhostOS, Rust, vision, audio, Torch, or sentence-transformers stack.

## Run

```bash
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567
```

Set `GITHUB_TOKEN` for private repositories. v0.1 accepts only `github.com` PR URLs and `api.github.com`; custom API hosts are rejected so a GitHub token cannot be redirected to an untrusted server. The token is never written to the bundle.

The collector checks the PR head before evidence collection and repeats the head check after collection. A force-push during the audit produces `HOLD` or `INCOMPLETE`, never PASS. Exact-head identity is not waivable through human adjudication.

The first run produces `adjudication-template.json`. Complete it and rerun with `--adjudication adjudication.json`. A human PASS cannot silently upgrade incomplete evidence: every accepted `NOT_RUN` or `INCOMPLETE` lane must include a reason.

The output contains `manifest.json`, `scorecard.json`, `SCORECARD.md`, and bounded files under `evidence/`. The manifest binds evidence digests and both Scorecard representations. Changed-file patches remain local and should be treated as repository-sensitive data.

`--overwrite` is accepted only when the target already contains a valid advisory LS audit manifest. Symbolic-link output paths are rejected. A primary API or filesystem failure removes only an unsealed partial output; a completed manifest is never deleted by cleanup.

The CLI is advisory-only. It cannot approve or merge a PR.

## Exit codes

- `0`: bundle produced; inspect the Scorecard verdict.
- `2`: invalid input or adjudication.
- `3`: initial or final exact-head mismatch; collection is fail-closed.
- `4`: primary GitHub API request failed.
- `5`: local filesystem operation failed.
