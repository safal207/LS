# LS Exact-Head PR Risk Audit — Operator Runbook

## Purpose

Produce a frozen, advisory-only evidence bundle for one GitHub.com pull request at one operator-supplied 40-character head SHA.

The CLI does not install or invoke the legacy GhostOS, Rust, vision, audio, or ML stack. It does not call AI models and has no merge authority.

## Clean-room path

```bash
git clone https://github.com/safal207/LS.git
cd LS
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install ./packages/ls-audit-cli
export LS_TOOL_SOURCE_SHA="$(git rev-parse HEAD)"
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567
```

`LS_TOOL_SOURCE_SHA` binds the bundle to the exact LS source revision used by the operator. It must be a full 40-character hexadecimal SHA. The final `manifest.json` and `scorecard.json` record this value and include it in the bundle digest. In GitHub Actions, LS also records available repository, workflow, run ID, and run-attempt metadata.

For a private target repository:

```bash
export GITHUB_TOKEN=...
```

The CLI accepts only `github.com` PR URLs and the fixed `https://api.github.com` API boundary. Custom hosts and custom API bases are rejected before the token is used. The token is never persisted in the bundle.

## Optional CML Git Internet lane

To add reviewed public causal memory, provide an explicit local registry:

```bash
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567 \
  --cml-registry packages/ls-audit-cli/examples/cml-trust-registry.v0.1.json
```

Every registry source is a GitHub `owner/repo` plus an exact 40-character commit. LS uses a separate anonymous client for those cross-repository public reads; the target repository's `GITHUB_TOKEN` is never forwarded to a CML source.

The CML lane independently checks:

- `cml-memory-pack-v1` schema and exact known fields;
- canonical SHA-256 `pack_id`;
- repository and source-commit binding;
- graph and selected-path integrity;
- evidence references;
- `visibility=public` and `contains_private_data=false`;
- absence of merge and execution authority.

The frozen PR title and changed filenames form a deterministic query. Up to three public memories are written to `evidence/cml-memory.json` and shown in the Scorecard. Non-public or invalid paths and counts are not disclosed.

CML is advisory context only. A `PASS` causal-memory lane cannot independently upgrade the audit verdict. A configured source that cannot be verified produces an `INCOMPLETE` lane, which follows the existing explicit human-acceptance rules.

When `--cml-registry` is absent, no CML network request or lane is created.

## First result

The first run creates:

```text
manifest.json
scorecard.json
SCORECARD.md
adjudication-template.json
evidence/
```

With CML enabled, `evidence/` also contains `cml-memory.json`. The manifest binds its digest, SHA-256 digests for `scorecard.json` and `SCORECARD.md`, and the exact LS tool source SHA when supplied.

The CLI verifies the expected target head twice:

1. before secondary evidence collection;
2. after evidence collection completes.

If either observed target head differs from the supplied SHA, the verdict is `HOLD`. If the final recheck cannot run, it is `INCOMPLETE`; the bundle cannot support PASS. Initial and final exact-head identity are non-waivable gates.

The official pull-request workflows separately check out `github.event.pull_request.head.sha` rather than GitHub's synthetic merge ref and assert that `git rev-parse HEAD` equals the expected source SHA before tests execute.

If the target head remains stable, available changed-file, review, commit-status, and check-run evidence is frozen. Missing API access and detected pagination/truncation boundaries become `INCOMPLETE`, never success.

Review submission semantics are exact-head and fail-closed. The latest submission per reviewer determines that reviewer's current state:

- current `CHANGES_REQUESTED` → `FAIL / HOLD`;
- current `APPROVED` → positive review signal;
- `COMMENTED`, stale-head, missing, dismissed, or unavailable review evidence → `INCOMPLETE` or `NOT_RUN`.

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

A hard primary target API or local filesystem failure cleans up only an unsealed partial directory. Once `manifest.json` exists, automatic failure cleanup does not remove the bundle. Optional CML source failures are preserved as generic `INCOMPLETE` evidence rather than deleting the primary audit.

## Local verification

```bash
PYTHONPATH=packages/ls-audit-cli \
  python -m unittest discover -s packages/ls-audit-cli/tests -v
python -m pip install ./packages/ls-audit-cli
ls-audit --help
```

The implementation is standard-library-only at runtime. Build tooling is limited to setuptools and wheel.

The path-scoped GitHub workflow installs the package on a clean Python 3.11 runner checked out at the exact pull-request head, asserts source identity, and audits its own pull request at that same event head. The live path also reads the example CML source at its pinned commit, verifies the CML evidence digest and no-authority fields, and must finish within 15 minutes.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Bundle produced; inspect the Scorecard verdict. |
| `2` | Invalid operator input, target boundary, registry, overwrite target, adjudication, or tool source SHA. |
| `3` | Initial or final exact-head mismatch; the audit is fail-closed. |
| `4` | Primary target GitHub API request failed. |
| `5` | Local filesystem or provenance-stamping failure. |
