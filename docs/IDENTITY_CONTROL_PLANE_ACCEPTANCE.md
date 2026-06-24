# LS Identity Control Plane — Acceptance Runbook

This runbook verifies the complete governed identity path from repeated verified
experience to an automatically published, read-only identity generation.

## What the acceptance command proves

The deterministic scenario creates two agents. Each agent receives three
immutable `VerifiedEpisode` records supporting one bounded lesson. The path is:

```text
VerifiedEpisode x3
  -> LessonAggregation
  -> IdentityUpdateProposal
  -> independent Approval
  -> IdentityProfilePatch
  -> durable PatchCommit
  -> one-time ProfileActivation
  -> append-only Identity Timeline
  -> content-addressed Timeline Commit Receipt
  -> hash-chained Publication Outbox
  -> atomic signed Catalog Generation
  -> read-only Control Plane Viewer
```

The first governed agent commit publishes Generation 1. Processing the same
outbox again is a no-op. A second governed agent commit publishes exactly
Generation 2 and chains the Generation 1 publication digest.

## Run the acceptance bundle

Set an external keyring. Test material is shown only as an example; production
keys must come from the deployment secret store.

```bash
export LS_IDENTITY_CATALOG_KEYRING_JSON='{
  "acceptance-key": "replace-with-external-key-material"
}'

PYTHONPATH=.:python:python/modules \
python scripts/run_identity_control_plane_acceptance.py \
  --output-root build/identity-control-plane-acceptance \
  --active-key-id acceptance-key \
  --signing-key-id acceptance-key \
  --audience internal \
  --reset
```

Expected summary:

```json
{
  "result": "PASS",
  "first_generation": 1,
  "identical_replay_generation": 1,
  "second_generation": 2
}
```

## Reviewer evidence

The generated directory contains:

- `identity-control-plane-acceptance.json` — complete manifest and file digests;
- `reviewer-summary.json` — compact result;
- `governed-records/` — episodes, proposal, approval, patch, commit, application,
  and profile versions;
- `identity-data/` — append-only event stores, deterministic timelines, and
  timeline commit receipts;
- `identity-catalog-publication-outbox.jsonl` — durable publication requests;
- `publisher/` — immutable Generation 1 and Generation 2 plus the current signed
  catalog;
- `trigger/` — checkpoint, health, and causal trigger metadata;
- `api/` — read-only API response exports;
- `dashboard/` — accessible responsive reviewer interface;
- `tamper-report.json` — fail-closed boundary checks.

## Required checks

1. Validate `identity-control-plane-acceptance.json` against
   `schemas/trusted_runtime/identity_control_plane_acceptance.schema.json`.
2. Confirm both agents contain exactly three verified episodes.
3. Confirm proposer and approver actors differ.
4. Confirm every activation references a durable patch commit.
5. Scan both `identity-events.jsonl` files and the publication outbox hash chain.
6. Confirm the trigger state and current publication agree on Generation 2 and
   publication digest.
7. Confirm the latest trigger batch contains the second agent request ID and
   durable tail event reference.
8. Confirm `pending_request_count == 0` and
   `quarantined_request_count == 0`.
9. Confirm both API timeline exports report `authoritative == true` and active
   profile version 2.
10. Confirm the dashboard JavaScript only issues `GET` requests and the WSGI API
    rejects mutation methods with `405`.
11. Confirm the tamper suite detects changes to timeline, outbox, catalog, and
    trigger metadata.

## Fail-closed expectations

- A changed timeline digest with unchanged receipt cannot become authoritative.
- A broken outbox hash chain stops trigger processing.
- A changed signed catalog fails verification.
- A changed trigger-batch digest makes Control Plane status non-authoritative.
- Missing or incomplete bundles remain pending or quarantined.
- Re-delivering an existing request returns the original durable event ref.
- Restart after publication but before checkpoint resumes the same generation.

## Stacked PR merge order

Merge only after each dependency is green, in this order:

1. `#623` Trusted PR Review MVP
2. `#626` Agent Orientation projection
3. `#628` Agent Orientation artifacts
4. `#629` Verified Episode foundation
5. `#631` Governed identity proposal aggregation
6. `#633` Approval, patch, activation, and rollback
7. `#635` Append-only identity lifecycle replay
8. `#639` Read-only Identity Timeline viewer
9. `#642` Signed live identity catalog
10. `#645` Atomic monotonic catalog publisher
11. `#647` Durable timeline commit trigger
12. Acceptance PR implementing issue `#648`

Do not squash or reorder stacked branches without re-running the complete matrix,
because each layer's evidence and base branch are part of the review contract.

## Security boundary

The dashboard and its API are observational. They cannot approve proposals,
create patches, activate profiles, invalidate approvals, or roll back identity.
Privileged governance operations remain separate from the viewer and catalog
publisher.
