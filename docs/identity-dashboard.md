# Identity Dashboard

## Status

Design and product contract for the LS identity review surface.

This document follows:

- `docs/identity-snapshot.md`;
- `docs/snapshot-reconstruction.md`;
- `docs/identity-proposal-candidate.md`;
- `docs/governance-handoff.md`;
- `docs/identity-update-record.md`;
- `docs/rollback-ledger.md`;
- issue `#742`.

## 1. Purpose

The Identity Dashboard is the human-facing, read-only surface over a reconstructed `IdentitySnapshot`.

It answers:

- who the agent is now;
- which identity influences are active;
- which proposals are waiting for review;
- which influences are quarantined, expired, rolled back, or superseded;
- why each visible claim exists;
- what changed between two snapshots;
- which bounded review action a human may request next.

Core principle:

> A reconstructed identity is only safe if a human can inspect it, challenge it, and govern its future changes.

## 2. Core boundary

```text
IdentityUpdateRecord + RollbackLedger
  -> IdentitySnapshot
  -> Identity Dashboard (read-only)
  -> IdentityReviewAction
  -> independent governance / rollback workflow
```

The dashboard is not a governance actor.

```text
Dashboard display != governance decision
Dashboard button != identity mutation
IdentityReviewAction != IdentityUpdateApproval
```

The dashboard MUST NOT directly:

- approve an identity update;
- create a profile patch;
- apply an identity influence;
- activate a profile;
- mutate stable identity;
- grant execution, tool, policy, or delegation authority;
- rewrite or delete rollback history.

Every control emits an auditable `IdentityReviewAction` bound to the exact snapshot and target material inspected by the reviewer.

## 3. Source of truth

The primary read model is `IdentitySnapshot`.

The dashboard MUST NOT reconstruct identity independently from free-form notes or UI state. It consumes a snapshot produced by the reconstruction layer and preserves:

- `snapshot_id`;
- `snapshot_time` and reconstruction `as_of` time;
- snapshot digest;
- included and excluded scopes;
- active influences;
- quarantined influences;
- recent rollbacks and supersessions;
- provenance summary;
- warnings and uncertainty markers.

A missing or invalid snapshot digest makes all mutating review controls unavailable.

## 4. State separation

The interface MUST render identity states as separate collections. They may never be collapsed into one undifferentiated list.

Required state families:

- `active` — governed influence currently present in the reconstructed identity;
- `proposed` / `under_review` — candidate influence not yet active;
- `quarantined` — proposal or update isolated pending investigation;
- `rolled_back` — previously active influence explicitly reversed;
- `superseded` — historical influence replaced by a newer governed record;
- `expired` — influence or proposal outside its validity window;
- `uncertain` — reconstruction cannot deterministically choose a current state.

Rolled-back, superseded, expired, quarantined, or merely proposed influences MUST NOT be presented as active identity.

## 5. Required dashboard sections

### 5.1 Current identity summary

A compact answer to “Who is this agent now?” grouped by track family, for example competence, trust, preferences/values, relationship memory, and governance-risk constraints.

Every item shows:

- influence label and machine key;
- state;
- continuity level and target scope;
- update reference;
- effective and expiry times where present;
- bounded allowed effect;
- forbidden effects;
- provenance status.

### 5.2 Review queue

Shows `IdentityProposalCandidate` or review-only runtime proposals that are not active.

Each row MUST display:

- proposal/candidate reference and digest;
- source aggregation reference and digest;
- proposed identity influence;
- support, failure, contradiction, and counterevidence counts;
- scope;
- expiry;
- review reason;
- rollback plan availability;
- intake outcome and readiness state.

### 5.3 Quarantine and uncertainty

Shows malformed, disputed, scope-inflating, provenance-weak, or contradictory identity material. The UI must explain why the material is not active.

### 5.4 Rollback and supersession history

Shows explicit ledger transitions. Rollback is rendered as a new historical event, never as deletion.

### 5.5 Provenance drawer

Every visible influence or proposal opens a provenance view containing:

```text
VerifiedEpisode
  -> TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdateRecord
  -> optional RollbackLedger entry
  -> IdentitySnapshot influence
```

Missing links are shown as a broken chain, not silently hidden.

### 5.6 Snapshot comparison

The dashboard supports comparison between snapshot A and snapshot B.

The diff view distinguishes activated influences, deactivated influences, changed values, scope changes, new or removed warnings, rollback and supersession transitions, and provenance changes.

A diff is descriptive. It does not authorize a transition.

## 6. Scope visibility

Scope is always visible and filterable.

Supported continuity levels:

- `individual`;
- `relational`;
- `shared_memory`;
- `system`.

Relational identity must show the relationship reference. A local or relational influence must never appear as global identity merely because the user changed the dashboard filter.

The UI SHOULD visually warn on any proposed scope expansion.

## 7. Review controls

Supported controls:

- `approve`;
- `reject`;
- `rollback`;
- `quarantine`;
- `request_more_evidence`;
- `supersede`;
- `annotate`.

The labels describe reviewer intent, not immediate identity effects.

| UI intent | Emitted handoff |
|---|---|
| `annotate` | `RECORDED_ONLY` |
| `approve`, `reject`, `quarantine`, `request_more_evidence`, `supersede` | `ROUTE_TO_GOVERNANCE` |
| `rollback` | `ROUTE_TO_ROLLBACK_GOVERNANCE` |

No action may return `IDENTITY_APPLIED` directly from the dashboard endpoint.

## 8. Exact binding and stale-view protection

Every action binds to:

- exact snapshot ID and digest;
- snapshot reconstruction time;
- exact target reference and digest;
- target state observed by the reviewer;
- target scope;
- visible provenance and evidence references;
- authenticated actor;
- reason;
- idempotency key.

Before routing an action, the server re-checks current snapshot and target digests.

If either changed, the action outcome is:

```text
REVALIDATE_SNAPSHOT
```

The reviewer must inspect the refreshed state. A stale “Approve” click cannot approve new material that was not displayed.

## 9. Explainability and uncertainty

The dashboard MUST surface broken provenance, retained counterevidence, unresolved contradictions, scope boundaries, open rollback risk, stale snapshot state, and reconstruction warnings.

Unknown or contradictory identity state is shown as uncertainty. The UI must not invent a stable summary to fill an empty card.

## 10. Privacy and access

The dashboard applies scope-aware access control before returning snapshot content.

In particular:

- relational overlays are visible only to authorized relationship participants/reviewers;
- shared-memory and system scopes may require stronger review roles;
- raw evidence is not expanded when the reviewer only has summary access;
- exported views preserve redaction markers and never imply missing evidence does not exist.

## 11. Suggested API boundary

```text
GET  /api/identity/snapshot
GET  /api/identity/snapshot/{snapshot_id}
GET  /api/identity/snapshot/compare?from=...&to=...
POST /api/identity/review-actions
GET  /api/identity/review-actions/{action_id}
```

GET endpoints are read-only.

POST creates an `IdentityReviewAction` audit event and returns one of:

- `RECORDED_ONLY`;
- `ROUTE_TO_GOVERNANCE`;
- `ROUTE_TO_ROLLBACK_GOVERNANCE`;
- `REVALIDATE_SNAPSHOT`;
- `REJECT`.

It never applies identity directly.

## 12. Fail-closed behavior

Disable review controls and surface an error when:

- snapshot or target digest is missing;
- target scope is missing;
- provenance is broken;
- action target is not present in the bound snapshot/review queue;
- reviewer role is insufficient;
- current state differs from displayed state;
- action would silently drop counterevidence;
- rollback target has no applied update/application binding;
- action envelope requests authority or direct mutation.

## 13. Product acceptance criteria

A conforming surface:

- clearly separates active and non-active identity;
- explains every active influence;
- preserves scope and relational boundaries;
- supports point-in-time comparison;
- emits audited, digest-bound review actions;
- revalidates stale snapshots;
- routes governance and rollback instead of applying identity;
- retains history after rollback and supersession;
- never presents review intent as completed identity mutation.
