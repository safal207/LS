# Human Review Workflow for Identity State

## Status

Normative workflow guidance for `IdentityReviewAction` submission from the Identity Dashboard defined in issue `#742`.

## 1. Goal

Allow a human or authorized reviewing agent to inspect, challenge, annotate, and request governed changes to reconstructed identity without turning the dashboard into an identity mutation authority.

## 2. Workflow

```text
1. Load exact IdentitySnapshot
2. Inspect scope, state, provenance, evidence, counterevidence, warnings
3. Select one exact target
4. Choose bounded review intent
5. Create digest-bound IdentityReviewAction
6. Revalidate snapshot and target material
7. Record action idempotently
8. Route to governance / rollback workflow, or record annotation only
9. Reconstruct a new snapshot after any downstream ledger transition
```

The original snapshot remains immutable and queryable.

## 3. Review preconditions

Before controls are enabled, the surface verifies:

- authenticated actor and review role;
- snapshot ID, digest, and reconstruction time;
- target reference, digest, observed state, and scope;
- provenance chain visibility;
- evidence and counterevidence summary visibility;
- target action compatibility;
- no unresolved stale-view marker.

A reviewer must never approve material they did not inspect.

## 4. Action semantics

### `annotate`

Adds a human explanation, correction, or review note.

- creates an immutable audit event;
- does not change candidate, update, application, or snapshot state;
- handoff: `RECORDED_ONLY`.

### `approve`

Expresses intent to approve an eligible proposal for independent governance processing.

- target: proposal candidate or review-only runtime proposal;
- requires exact proposal/candidate digest;
- does not set approval state;
- handoff: `ROUTE_TO_GOVERNANCE`.

### `reject`

Requests a governed rejection of the exact proposal material reviewed.

- preserves proposal and evidence history;
- does not delete the candidate;
- handoff: `ROUTE_TO_GOVERNANCE`.

### `quarantine`

Requests isolation pending investigation. Typical reasons include provenance break, unexplained scope inflation, memory-laundering suspicion, contradictory evidence channels, or policy-sensitive identity claims.

Handoff: `ROUTE_TO_GOVERNANCE`.

### `request_more_evidence`

Records that the shape may be valid but evidence is insufficient or materially contradicted.

- must name missing or weak evidence;
- existing evidence remains queryable;
- handoff: `ROUTE_TO_GOVERNANCE`.

### `supersede`

Requests explicit replacement by a newer proposal or update.

- requires `superseding_target_ref` and digest;
- old record remains historical;
- handoff: `ROUTE_TO_GOVERNANCE`.

### `rollback`

Requests reversal of an applied identity update/application.

- target must be an `IdentityUpdateRecord` or `IdentityApplication`;
- requires application/update binding and rollback plan reference;
- creates no deletion;
- does not mark the update rolled back directly;
- handoff: `ROUTE_TO_ROLLBACK_GOVERNANCE`.

## 5. Exact material binding

The action binds the reviewer decision to the material displayed at review time.

Required bindings:

- `snapshot_id`;
- `snapshot_digest`;
- `snapshot_time` and reconstruction `as_of`;
- target kind, reference, digest, observed state, and scope;
- provenance references shown to the reviewer;
- support, failure, contradiction, counterevidence, and supersession references considered;
- reviewer actor and role;
- action reason;
- action creation time;
- idempotency key.

Any change to snapshot, target material, evidence set, scope, proposed influence, rollback plan, or expiry invalidates the old review binding.

## 6. Stale snapshot handling

The receiving endpoint compares submitted digests with current authoritative material.

If the snapshot or target changed:

```text
submitted review action
  -> REVALIDATE_SNAPSHOT
  -> refresh UI
  -> show diff
  -> require new human confirmation
```

The old action remains in the audit trail with `not_routed_stale_binding` status.

## 7. Actor separation

The dashboard records reviewer intent. Independent governance remains responsible for the actual decision.

Required separation:

- continuity coordinator cannot approve its own proposal;
- proposer identity remains visible;
- reviewer identity is authenticated;
- governance decision actor is recorded separately;
- application executor is recorded separately;
- rollback actor and rollback authorizer are distinguishable.

A reviewer action may be one input to governance; it is not the governance result itself.

## 8. Idempotency

Every action carries a stable `idempotency_key` scoped to:

```text
actor + action + snapshot_digest + target_digest
```

Repeated delivery returns the original action record and routing state. It must not create duplicate approvals, rollbacks, annotations, or ledger transitions.

## 9. Audit record

An accepted action record preserves:

- raw submitted envelope;
- canonical action digest;
- authenticated actor;
- server receipt time;
- revalidation result;
- routing outcome;
- governance/rollback case reference if created;
- final downstream outcome reference when later available;
- no-direct-mutation flags.

Audit records are append-only. Corrections create a new annotation or superseding action.

## 10. Review reason requirements

Every action requires a structured reason code and human-readable explanation.

Suggested reason codes:

- `evidence_sufficient`;
- `evidence_insufficient`;
- `material_counterevidence`;
- `scope_inflation`;
- `broken_provenance`;
- `stale_identity_influence`;
- `human_correction`;
- `policy_change`;
- `newer_governed_material`;
- `annotation_only`.

Free-form text alone must not select an identity operation.

## 11. Review-action outcomes

### `RECORDED_ONLY`

Annotation stored. No governance or identity transition requested.

### `ROUTE_TO_GOVERNANCE`

Action stored and forwarded to an independent governance case. No approval/application has occurred.

### `ROUTE_TO_ROLLBACK_GOVERNANCE`

Rollback request stored and forwarded to rollback authorization. No rollback ledger entry has been committed yet.

### `REVALIDATE_SNAPSHOT`

Displayed material is stale. No routing or identity transition occurs.

### `REJECT`

Malformed, unauthorized, self-authorizing, scope-ambiguous, provenance-broken, or direct-mutation request. No routing or identity transition occurs.

## 12. Fail-closed matrix

| Condition | Result |
|---|---|
| missing snapshot or target digest | `REJECT` |
| target not in submitted snapshot/review queue | `REJECT` |
| target scope missing | `REJECT` |
| current digest differs from submitted digest | `REVALIDATE_SNAPSHOT` |
| actor lacks review role | `REJECT` |
| `approve` embeds approval/application state | `REJECT` |
| `rollback` lacks applied update/application binding | `REJECT` |
| `supersede` lacks replacement reference/digest | `REJECT` |
| annotation is complete and current | `RECORDED_ONLY` |
| valid proposal review intent | `ROUTE_TO_GOVERNANCE` |
| valid rollback request | `ROUTE_TO_ROLLBACK_GOVERNANCE` |

## 13. Downstream completion

When governance or rollback later commits a transition:

1. append the decision/update/rollback records;
2. preserve links back to the originating `IdentityReviewAction`;
3. reconstruct a new `IdentitySnapshot`;
4. show a before/after diff;
5. keep the old snapshot and action queryable.

The UI must not optimistically display identity as changed before this chain completes.

## 14. Core invariant

```text
human review intent
  -> audited action
  -> exact binding revalidation
  -> independent governance
  -> governed ledger transition
  -> reconstructed snapshot
```

> Human control is real only when the human can challenge identity state without bypassing the governance that keeps that state trustworthy.
