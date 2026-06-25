# RollbackLedger

## Status

Design note for LS continuity architecture.

This document defines the rollback ledger for governed identity updates.

It follows:

- `docs/identity-update-record.md`
- `docs/governance-handoff.md`
- `schemas/identity_update_record.example.json`
- issue `#721`

---

## 1. Core boundary

Rollback is not deletion.

```text
IdentityUpdateRecord(active)
  -> RollbackLedgerEntry(rolled_back | superseded | quarantined | revalidated)
```

A rollback ledger records how the active effect of an identity update changes over time while preserving the full audit trail.

---

## 2. Why a rollback ledger exists

Governed identity updates must remain reversible.

A single `IdentityUpdateRecord` captures one approved identity influence, but LS also needs a durable record of what happened *after* that approval:

- whether the update stayed active;
- whether it was superseded;
- whether it was rolled back;
- whether it was quarantined;
- whether it was revalidated;
- which new evidence triggered the change.

Without a rollback ledger, LS risks treating approved identity updates as permanent facts instead of governed, revisable state.

---

## 3. Ledger responsibilities

The rollback ledger should answer:

- which identity update changed state;
- what transition happened;
- why it happened;
- which evidence, correction, or governance action triggered it;
- whether the update is still active;
- whether another update superseded it;
- whether a rollback was full or partial;
- how the current active identity state can be reconstructed.

---

## 4. Ledger entry types

Suggested rollback ledger entry classes:

- `rollback`
- `supersession`
- `quarantine`
- `revalidation`
- `expiration`
- `human_correction`
- `policy_override`

These are ledger transitions, not original identity updates.

---

## 5. Minimum fields for a ledger entry

Candidate fields:

- `ledger_entry_id`
- `created_at`
- `created_by`
- `entry_type`
- `target_identity_update_ref`
- `prior_active_state`
- `new_active_state`
- `reason`
- `trigger_type`
- `trigger_refs`
- `governance_decision_ref`
- `superseding_update_ref`
- `rollback_scope`
- `notes`

---

## 6. Active-state transitions

Typical transitions:

- `active -> rolled_back`
- `active -> superseded`
- `active -> quarantined`
- `quarantined -> active`
- `active -> expired`
- `rolled_back -> under_review` (rare, if rollback itself is being reconsidered)

The ledger should preserve both the prior and new active state.

---

## 7. Rollback triggers

Rollback or state-transition triggers may include:

- new material counterevidence;
- human correction;
- policy change;
- repeated failure after approval;
- evidence channel reclassification;
- consent withdrawal;
- scope inflation detected;
- a superseding governance decision;
- expiry of a time-bounded update.

Triggers should be recorded explicitly, not inferred later.

---

## 8. Supersession vs rollback

### Supersession

Use when a newer identity update replaces or narrows an older one.

Examples:

- a stronger competence update replaces an older weaker one;
- a preference update replaces a prior preference;
- a trust decrease supersedes a prior trust increase.

### Rollback

Use when the original update should no longer remain active because its basis is no longer valid or safe.

Examples:

- later evidence contradicts the approved pattern;
- a human explicitly corrects the update;
- policy changes invalidate the update’s scope.

Supersession and rollback both change active state, but they are not identical.

---

## 9. Partial rollback

Rollback may be full or partial.

Examples:

- full rollback: the entire update is deactivated;
- partial rollback: a competence increase remains valid locally but loses any broader relational effect.

`rollback_scope` should make this explicit.

Possible values:

- `full`
- `scope_narrowing`
- `confidence_reduction`
- `trust_only`
- `preference_only`

---

## 10. Fail-closed guards

A rollback ledger entry should fail closed when:

- `target_identity_update_ref` is missing;
- `prior_active_state` is missing;
- `new_active_state` is missing;
- the trigger is not recorded;
- the transition implies governance action but no governance decision ref exists;
- the entry claims supersession but no `superseding_update_ref` exists;
- the transition would silently delete identity history.

---

## 11. Reconstruction rule

The rollback ledger must support active-state reconstruction.

Given:

- all `IdentityUpdateRecord` objects,
- all rollback ledger entries,
- and supersession links,

LS should be able to determine:

1. which identity updates are currently active;
2. which were superseded;
3. which were rolled back;
4. why they changed state;
5. which proposal / governance decision chain led there.

---

## 12. Example flow

### Step 1 — approved update

An `IdentityUpdateRecord` grants a bounded competence-confidence increase for a publishing workflow.

### Step 2 — new contradiction

Two later `unexpected_verified` episodes show repeated failure in the same workflow family.

### Step 3 — governance review

Governance decides the original competence-confidence update should no longer remain active.

### Step 4 — rollback ledger entry

LS writes a ledger entry:

```text
entry_type = rollback
prior_active_state = active
new_active_state = rolled_back
trigger_type = new_material_counterevidence
trigger_refs = [vep_publish_006, vep_publish_007]
```

### Step 5 — current state

The original update remains in history, but it no longer contributes to active identity reconstruction.

---

## 13. Summary

The rollback ledger is the memory of identity correction.

It prevents this collapse:

```text
approved identity update == permanent identity fact
```

and replaces it with:

```text
approved update -> active state -> rollback / supersession / quarantine history
```

Core principle:

> Every governed identity repositioning must remain auditable, reversible, and reconstructable over time.
