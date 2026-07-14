# LS Exact-Head PR Risk Audit — Operator Runbook

## Purpose

Produce a frozen, advisory-only evidence bundle for one GitHub.com pull request at one operator-supplied 40-character head SHA.

The CLI does not install or invoke the legacy GhostOS, Rust, vision, audio, or ML stack. It does not call AI models and has no merge authority.

## Clean-room path

Native installation from a freshly cloned repository:

```bash
git clone https://github.com/safal207/LS.git
cd LS
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install ./packages/ls-audit-cli
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567
```

Docker clean-room path from a freshly cloned repository:

```bash
docker build -f packages/ls-audit-cli/Dockerfile -t ls-exact-head-audit .
docker run --rm \
  -e GITHUB_TOKEN \
  -v "$PWD/audit-output:/audit-output" \
  ls-exact-head-audit \
  https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567 \
  --output /audit-output/pr-123
```

For a private repository:

```bash
export GITHUB_TOKEN=...
```

v0.1 accepts only `github.com` PR URLs and the fixed `https://api.github.com` API boundary. Custom hosts and custom API bases are rejected before the token is used. The token is never persisted in the bundle.

## First result

The first run creates:

```text
manifest.json
scorecard.json
SCORECARD.md
adjudication-template.json
evidence/
```

The manifest binds the evidence digests plus SHA-256 digests for `scorecard.json` and `SCORECARD.md`.

The CLI verifies the expected head twice:

1. before secondary evidence collection;
2. after evidence collection completes.

If either observed head differs from the supplied SHA, the verdict is `HOLD`. If the final recheck cannot run, it is `INCOMPLETE`; the bundle cannot support PASS. Initial and final exact-head identity are non-waivable gates.

If the head remains stable, available changed-file, review, commit-status, and check-run evidence is frozen. Missing API access and detected pagination/truncation boundaries become `INCOMPLETE`, never success.

Review submission semantics are exact-head and fail-closed. The latest submission per reviewer determines that reviewer's current state:

- current `CHANGES_REQUESTED` → `FAIL / HOLD`;
- current `APPROVED` → positive review signal;
- `COMMENTED`, stale-head, missing reviewer provenance, dismissed, or unavailable review evidence → `INCOMPLETE` or `NOT_RUN`.

The Scorecard also emits sorted deterministic `reason_codes` so judges can see why the bundle is not passable without re-deriving policy from raw JSON. Examples include `FINAL_EXACT_HEAD_MISMATCH_STALE_EVIDENCE`, `REVIEWER_PROVENANCE_MISSING`, and `REQUIRED_LANE_INCOMPLETE_CHECK_RUNS`.

## Human adjudication

Complete the generated template and rerun:

```bash
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567 \
  --adjudication adjudication.json \
  --output final-audit
```

A human `PASS` cannot silently upgrade incomplete evidence. Every accepted `NOT_RUN` or `INCOMPLETE` lane must be named in `accepted_incomplete_lanes` with a non-empty reason. Finding dispositions are limited to `confirmed`, `rejected`, `scoped`, and `unresolved`.

## Data, overwrite, and failure boundary

`evidence/files.json` can contain source patches. Keep the output local and store it according to the target repository's data policy.

Do not edit a completed bundle in place. `--overwrite` is allowed only for a directory containing a valid advisory LS audit manifest. Symbolic-link output paths are rejected so the CLI cannot be used to delete an unrelated directory through the overwrite path.

A hard primary API or local filesystem failure cleans up only an unsealed partial directory. Once `manifest.json` exists, automatic failure cleanup does not remove the bundle.

## Local verification

```bash
PYTHONPATH=packages/ls-audit-cli \
  python -m unittest discover -s packages/ls-audit-cli/tests -v
python -m pip install ./packages/ls-audit-cli
ls-audit --help
docker build -f packages/ls-audit-cli/Dockerfile -t ls-exact-head-audit .
docker run --rm ls-exact-head-audit --help
```

The implementation is standard-library-only at runtime. Build tooling is limited to setuptools and wheel.

The path-scoped GitHub workflow resolves the pull-request source SHA, checks out that exact SHA, verifies `git rev-parse HEAD`, runs the focused test suite, builds the Docker image, and runs the container entrypoint. The job fails if the source SHA is missing or malformed, the checkout does not match, tests fail, or the Docker path cannot be reproduced.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Bundle produced; inspect the Scorecard verdict. |
| `2` | Invalid operator input, target boundary, overwrite target, or adjudication. |
| `3` | Initial or final exact-head mismatch; the audit is fail-closed. |
| `4` | Primary GitHub API request failed. |
| `5` | Local filesystem operation failed. |
