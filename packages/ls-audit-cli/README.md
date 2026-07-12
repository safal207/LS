# LS Exact-Head Audit CLI

A standard-library-only operator CLI that freezes bounded GitHub evidence for one pull request at one exact 40-character head SHA.

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

Set `GITHUB_TOKEN` for private repositories. The token is never written to the bundle.

The first run produces `adjudication-template.json`. Complete it and rerun with `--adjudication adjudication.json`. A human PASS cannot silently upgrade incomplete evidence: every accepted `NOT_RUN` or `INCOMPLETE` lane must include a reason.

The output contains `manifest.json`, `scorecard.json`, `SCORECARD.md`, and bounded files under `evidence/`. Changed-file patches remain local and should be treated as repository-sensitive data.

The CLI is advisory-only. It cannot approve or merge a PR.

## Exit codes

- `0`: bundle produced; inspect the Scorecard verdict.
- `2`: invalid input or adjudication.
- `3`: exact-head mismatch; secondary collection stopped fail-closed.
- `4`: primary GitHub API request failed.
