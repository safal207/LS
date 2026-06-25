# Snapshot Reconstruction

## Status

Design note for LS continuity architecture.

This document defines how LS reconstructs an `IdentitySnapshot` from governed identity records and rollback history.

It follows:

- `docs/identity-snapshot.md`
- `docs/identity-update-record.md`
- `docs/rollback-ledger.md`
- `schemas/identity_snapshot.example.json`
- issue `#727`

---

## 1. Goal

Snapshot reconstruction answers a practical question:

> **What is the active identity of this agent at time T?**

The answer must be derived from governed artifacts, not guessed from recent memory alone.

---

## 2. Inputs

Reconstruction consumes at least:

- `IdentityUpdateRecord` objects;
- rollback ledger entries;
- supersession links;
- point-in-time target `T`;
- optional scope filter.

Optional later inputs may include:

- quarantine registries;
- trust-policy overlays;
- relational-view filters.

---

## 3. Output

The output is an `IdentitySnapshot` containing:

- active identity influences at time `T`;
- quarantined or inactive items separated from active identity;
- provenance summary;
- warnings / unresolved contradictions if needed.

---

## 4. Core reconstruction rule

Start from all governed identity updates that existed at or before time `T`.

Then remove or downgrade any update that, before or at `T`, was:

- rolled back;
- superseded;
- expired;
- quarantined from active use;
- otherwise marked inactive by a valid ledger transition.

What remains becomes the candidate active identity set.

---

## 5. Step-by-step algorithm

## Step 1 — collect eligible updates

Select all `IdentityUpdateRecord` objects where:

- `applied_at <= T`
- scope matches the requested snapshot scope (if a scope filter is present)

Ignore updates created after `T`.

---

## Step 2 — attach later state transitions up to T

For each eligible update, gather rollback-ledger entries affecting that update where:

- ledger entry timestamp `<= T`

This yields the update’s state history up to the requested time.

---

## Step 3 — resolve active state

For each update, resolve its effective state at time `T`.

Typical resulting states:

- `active`
- `rolled_back`
- `superseded`
- `quarantined`
- `expired`
- `under_review`

If multiple ledger transitions exist, the latest valid transition at or before `T` wins.

---

## Step 4 — build active identity set

Only updates whose effective state at `T` is `active` should enter the active identity set.

All others should be excluded from active identity and optionally placed into summary sections such as:

- `quarantined_influences`
- `recent_rollbacks`
- `recent_supersessions`

---

## Step 5 — group active influences by semantic family

Group active updates into snapshot sections such as:

- competence
- trust
- preferences
- relationship memory
- governance risk / constraints

This grouping is a presentation layer over the active update set, not a replacement for provenance.

---

## Step 6 — preserve provenance

For every active influence, attach enough provenance to answer:

- which update made it active;
- which proposal requested it;
- which governance decision approved it;
- what track / scope it belongs to.

If provenance is broken, reconstruction should fail closed or surface uncertainty.

---

## 6. Scope filtering

A snapshot may be reconstructed for different views.

Examples:

- **individual snapshot** — only individual-scope identity updates
- **Alex-relational snapshot** — individual + relational updates relevant to Alex
- **system snapshot** — system-level trust / policy / governance markers

Scope filtering must happen before final materialization.

LS must not silently mix relational identity with system identity.

---

## 7. Supersession handling

Superseded updates must not remain active identity unless the superseding chain itself says otherwise.

Rule:

```text
if update A is superseded by update B before time T,
A is not active at T unless B was later rolled back in a way that explicitly reactivates A.
```

If reactivation semantics are not defined, LS should prefer caution and surface ambiguity instead of reviving A implicitly.

---

## 8. Rollback handling

Rolled-back updates must not remain in active identity.

They may still appear in historical or explanatory sections, but not in the active influence set.

If rollback is partial, reconstruction should apply the rollback scope precisely.

Example:

- a competence update remains active locally,
- but its broader relational effect is removed.

In that case the snapshot should materialize only the surviving portion.

---

## 9. Quarantine handling

Quarantined proposals or updates should not silently enter active identity unless governance explicitly reactivates them.

A snapshot may include a quarantine section, but quarantine is not active identity by default.

---

## 10. Expiration handling

If an identity update has an expiry condition and it expires before `T`, it should be treated as inactive unless later renewed.

Expiration should behave like a governed state transition, not as silent disappearance.

---

## 11. Conflict handling

Conflicts may appear when two active updates imply incompatible identity states.

Examples:

- one update says trust increased, another says trust decreased for the same scope;
- one preference update conflicts with a later constraint;
- provenance chains disagree about scope.

When conflicts exist, LS should prefer one of three outcomes:

1. **resolve deterministically** if the governance / ledger rules clearly decide precedence;
2. **surface uncertainty** if the conflict cannot be resolved safely;
3. **quarantine the conflicting active state** if governance policy requires caution.

LS should not silently fabricate harmony from contradictory updates.

---

## 12. Fail-closed rules

Snapshot reconstruction should fail closed when:

- active state cannot be determined;
- an active influence has no update ref;
- a rolled-back or superseded update still appears active;
- scope is missing;
- provenance is broken;
- contradictory transitions make active state ambiguous.

Fail closed may mean:

- refuse to materialize a “stable” snapshot;
- emit a snapshot with warnings and unresolved sections;
- require governance / human review.

---

## 13. Example reconstruction flow

### Input

At time `T = 2026-06-25T10:35:00Z`, LS has:

- a bounded competence update for publish-doc workflow;
- a strong competence update for governance contract reasoning;
- a fail-closed preference update;
- an older publish-doc competence update that was superseded;
- a prior system-level trust elevation that was rolled back.

### Reconstruction

1. collect all updates applied at or before `T`
2. attach rollback / supersession transitions up to `T`
3. resolve final state for each update
4. exclude the rolled-back trust elevation and the superseded older competence update
5. keep the bounded competence update, governance contract reasoning update, fail-closed preference, and allowed relational continuity markers
6. emit warnings that system-level trust elevation remains blocked

### Result

The snapshot shows:

- active publish-doc competence
- active governance contract reasoning competence
- active fail-closed preference
- active Alex-relational continuity
- no active system-level trust elevation

---

## 14. Summary

Snapshot reconstruction is the bridge from identity history to present-tense identity state.

It prevents this collapse:

```text
all identity history == active identity
```

and replaces it with:

```text
governed updates + rollback history + scope filters
  -> explicit active identity snapshot at time T
```

Core principle:

> The current identity center must be reconstructed from governed state, not improvised from memory fragments.
