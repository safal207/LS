# LS Exact-Head Audit CLI

A standard-library-only operator CLI that freezes bounded GitHub.com evidence for one pull request at one exact 40-character head SHA.

## Install

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install ./packages/ls-audit-cli
```

This package does not install the legacy GhostOS, Rust, vision, audio, Torch, sentence-transformers, embedding, or model stack.

## Run

Bind the audit result to both the target PR head and the exact LS source revision used to produce the bundle:

```bash
export LS_TOOL_SOURCE_SHA="$(git rev-parse HEAD)"
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567
```

`LS_TOOL_SOURCE_SHA` must be a full 40-character hexadecimal commit SHA. When present, LS writes it to both `manifest.json` and `scorecard.json`, includes it in the bundle digest, and records available GitHub Actions repository, workflow, run ID, and attempt metadata. The official CI workflow checks out this exact SHA and asserts `git rev-parse HEAD` before testing.

Set `GITHUB_TOKEN` for private target repositories. LS accepts only `github.com` PR URLs and `api.github.com`; custom API hosts are rejected. Both the target client and optional CML client reject HTTP redirects, so credentials and source trust cannot silently cross hosts. The target token is never written to the bundle.

The collector checks the PR head before evidence collection and repeats the head check after collection. A force-push during the audit produces `HOLD` or `INCOMPLETE`, never PASS. Exact-head identity is not waivable through human adjudication.

The first run produces `adjudication-template.json`. Complete it and rerun with `--adjudication adjudication.json`. A human PASS cannot silently upgrade incomplete evidence: every accepted `NOT_RUN` or `INCOMPLETE` lane must include a reason.

## Optional CML Git Internet evidence

Supply an explicit local registry to add public causal memory from repositories pinned to exact commits:

```bash
ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567 \
  --cml-registry packages/ls-audit-cli/examples/cml-trust-registry.v0.1.json
```

Registry format:

```json
{
  "schema_version": "ls.cml-trust-registry.v0.1",
  "sources": [
    {
      "repository": "safal207/Causal-Memory-Layer",
      "commit": "e84ba18b52ae697789071ceae816e467ab5f36de"
    }
  ]
}
```

The integration:

- requires one exact 40-character source commit and independently resolves it through GitHub before reading content;
- rejects a source when the resolved commit differs from the registry pin;
- uses a separate anonymous `api.github.com` client, never the target `GITHUB_TOKEN`;
- follows no HTTP redirects for either target or CML requests;
- independently validates `cml-memory-pack-v1`, canonical `pack_id`, graph connectivity, repository binding, privacy, and authority fields;
- accepts only repositories reported as public and packs with `visibility=public` plus `contains_private_data=false`;
- requires a bounded integer content size and validates the Base64 envelope length and padding before decoding;
- ranks up to three memories deterministically from the frozen PR title and changed filenames;
- writes `evidence/cml-memory.json` and a `Causal Memory` Scorecard section;
- never reveals hidden, non-public, or invalid pack paths or counts;
- never grants approval, execution, delivery, or merge authority.

A successful causal-memory lane is context only and cannot independently create `PASS`. An unavailable or invalid configured source makes the lane `INCOMPLETE`; normal LS human-adjudication rules then require explicit acceptance with a reason.

No CML network request occurs when `--cml-registry` is absent, when the initial exact-head gate fails, or when frozen changed-file evidence is incomplete.

## Bundle

The output contains `manifest.json`, `scorecard.json`, `SCORECARD.md`, and bounded files under `evidence/`. The manifest binds evidence digests, both Scorecard representations, and—when `LS_TOOL_SOURCE_SHA` is supplied—the exact tool source revision. Changed-file patches remain local and should be treated as repository-sensitive data.

`--overwrite` is accepted only when the target already contains a valid advisory LS audit manifest. Symbolic-link output paths are rejected. A primary API or filesystem failure removes only an unsealed partial output; a completed manifest is never deleted by cleanup.

The CLI is advisory-only. It cannot approve or merge a PR.

## Exit codes

- `0`: bundle produced; inspect the Scorecard verdict.
- `2`: invalid input, adjudication, or tool source SHA.
- `3`: initial or final exact-head mismatch; collection is fail-closed.
- `4`: primary target GitHub API request failed.
- `5`: local filesystem or provenance-stamping failure.
