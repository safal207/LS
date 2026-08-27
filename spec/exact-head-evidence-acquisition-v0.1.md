# Exact-head evidence acquisition v0.1

This layer freezes the immutable input for independent review. It does not analyze, execute, approve, comment on, or merge candidate code.

```text
manifest
-> verify live PR base/head and changed-file count
-> enumerate changed paths from compare(base SHA, head SHA)
-> verify comparison completeness against PR metadata
-> enforce ALL_CHANGED or declared-subset selection
-> admit explicit related paths
-> fetch inert text by exact commit SHA
-> re-check the PR after fetch
-> enforce byte bounds
-> record per-artifact provenance, Git blob SHA, and content SHA-256
-> canonicalize evidence
-> freeze evidence SHA-256
```

## Manifest

A manifest binds acquisition to:

- repository and pull-request number;
- expected base and head commit SHAs;
- expected changed-file count from PR metadata;
- exact changed artifact paths;
- a selection mode;
- optional related paths with source path, relation, and evidence;
- per-file and total byte limits.

`ALL_CHANGED` requires the direct artifact set to equal the complete commit-pinned comparison set. `DECLARED_SUBSET` permits a named subset but records that reduced scope in the evidence digest.

Branch names and mutable refs are not valid artifact identifiers.

## Fail-closed rules

Acquisition verifies the live base SHA, head SHA, and changed-file count before listing files. Changed paths are enumerated from the GitHub compare endpoint for the manifest base/head pair, never from the mutable PR Files endpoint. The number of unique compare paths must equal the PR metadata count. After every artifact has been fetched, the PR metadata is checked again. Any change, truncation, duplicate listing, malformed response entry, or incomplete comparison discards the bundle.

GitHub's compare response exposes at most 300 changed files. Acquisition therefore intentionally fails closed for a PR whose metadata count exceeds the complete compare listing; it never treats a capped 300-file response as full coverage.

It also rejects:

- absolute, aliased, traversal, duplicate, or backslash paths;
- direct paths not present in the exact commit comparison;
- omitted or extra changed paths under `ALL_CHANGED`;
- a changed artifact being relabeled as `RELATED`;
- related paths whose source is not a directly changed artifact;
- related paths without relation evidence;
- malformed pull-request, compare, or contents response objects;
- missing, empty, or wrongly typed response fields;
- Git blob SHAs that are not lowercase 40-character hashes;
- path mismatches in the GitHub response;
- redirects from GitHub API requests;
- non-UTF-8 API responses or artifact content;
- invalid JSON API responses;
- per-file or total evidence size overflow.

## Canonical evidence digest

Artifacts are ordered by repository path. Every artifact independently records:

- repository;
- PR number;
- exact base SHA;
- exact head SHA;
- repository path;
- Git blob SHA;
- content SHA-256;
- byte length;
- UTF-8 content;
- admission and relation provenance, including relation evidence.

The bundle evidence SHA-256 additionally covers schema version, changed-file count, selection mode, and the complete ordered artifact array.

Acquisition time is intentionally excluded, so independent acquisitions of the same bytes produce the same evidence digest.

## PR #796 calibration manifests

`benchmarks/exact-head/pr796-calibration-v0.1.json` preserves the earlier calibration point at head `a9bcc1c550f1139cd0233ecc8b05837d5c6d558c` with 17 changed files.

`benchmarks/exact-head/pr796-final-calibration-v0.1.json` is the benchmark input for the final merged PR head:

```text
base SHA:           66353d32cafe9a7e2e4b62ee98575859eca9f531
head SHA:           c482e19d829c39bdffa1352e8579c2362e7699c4
changed-file count: 19
selection mode:     ALL_CHANGED
```

The final head adds two artifacts that were absent from the earlier calibration point:

- `docs/product/approval-integrity-30-second-demo.md`;
- `tools/demo_approval_integrity.py`.

Both manifests contain no expected findings. A successful acquisition proves only that the selected exact-head files were frozen with reproducible provenance. Probe recall and comparison with Claude are separate benchmark stages.

The workflow defaults to the final-head manifest so a manual run cannot silently benchmark the earlier 17-file state.

## Workflow trust boundary

The pull-request job runs deterministic tests with an in-memory fake transport. Live GitHub acquisition is available only through `workflow_dispatch` on the repository default branch after the runtime has become trusted there.

The workflow accepts manifests only from `benchmarks/exact-head`, uses read-only `contents` and `pull-requests` permissions, and uploads the bundle as a workflow artifact. The REST client refuses redirects rather than forwarding authorization and wraps HTTP, transport, UTF-8, JSON, and response-shape failures with deterministic API-path or artifact-path context. Acquired content is never executed.
