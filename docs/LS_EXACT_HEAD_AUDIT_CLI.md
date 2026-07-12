# LS Exact-Head PR Risk Audit — Operator Runbook

## Purpose

Produce a frozen, advisory-only evidence bundle for one GitHub pull request at one operator-supplied 40-character head SHA.

The CLI does not install or invoke the legacy GhostOS, Rust, vision, audio, or ML stack. It does not call AI models and has no merge authority.

## Clean-room path

```bash
git clone https://github.com/safal207/LS.git
cd LS
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install ./packages/ls-audit-cli
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567
```

For a private repository:

```bash
export GITHUB_TOKEN=...
```

The token is used only as an HTTP Authorization header and is never persisted in the bundle.

## First result

The first run creates:

```text
manifest.json
scorecard.json
SCORECARD.md
adjudication-template.json
evidence/
```

If the observed PR head differs from the supplied SHA, exact-head status is `FAIL`, the verdict is `HOLD`, and secondary evidence collection stops.

If the head matches, available changed-file, review, commit-status, and check-run evidence is frozen. Missing API access is recorded in `evidence/api-errors.json` and becomes `INCOMPLETE`, never success.

## Human adjudication

Complete the generated template and rerun:

```bash
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567 \
  --adjudication adjudication.json \
  --output final-audit
```

A human `PASS` cannot silently upgrade incomplete evidence. Every accepted `NOT_RUN` or `INCOMPLETE` lane must be named in `accepted_incomplete_lanes` with a non-empty reason.

## Data boundary

`evidence/files.json` can contain source patches. Keep the output local, store it according to the target repository's data policy, and redact only by starting a new explicitly scoped audit. Do not edit a completed bundle in place.

## Local verification

```bash
PYTHONPATH=packages/ls-audit-cli \
  python -m unittest discover -s packages/ls-audit-cli/tests -v
python -m pip install ./packages/ls-audit-cli
ls-audit --help
```

The implementation is standard-library-only at runtime. Build tooling is limited to setuptools and wheel.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Bundle produced; inspect the Scorecard verdict. |
| `2` | Invalid operator input or adjudication. |
| `3` | Exact-head mismatch; secondary collection stopped fail-closed. |
| `4` | Primary GitHub API request failed. |
