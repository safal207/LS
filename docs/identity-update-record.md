# IdentityUpdateRecord

## Status

Design note for LS continuity architecture.

This document defines `IdentityUpdateRecord` as the governed, auditable record of an accepted identity influence.

It follows:

- `docs/identity-proposal-candidate.md`
- `docs/governance-handoff.md`
- `schemas/identity_proposal_candidate.example.json`
- issue `#721`

---

## 1. Core boundary

An identity update is not a proposal.

```text
IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdateRecord
```

`IdentityUpdateRecord` may exist only after an explicit governance decision approves an identity influence.

---

## 2. Why this object exists

Governance approval should not silently mutate identity state.

LS needs an explicit record that answers:

- what identity influence was applied;
- which proposal requested it;
- which governance decision approved it;
- what scope it affects;
- what evidence and counterevidence were preserved;
- what prior state it supersedes;
- how it can be rolled back;
- how current active identity state can be reconstructed.

---

## 3. Non-responsibilities

`IdentityUpdateRecord` must not:

- approve itself;
- erase the source proposal;
- erase counterevidence;
- delete previous identity history;
- hide rollback conditions;
- silently promote scope;
- make irreversible identity changes by default.

---

## 4. Minimum fields

Candidate fields:

- `identity_update_id`
- `update_version`
- `created_at`
- `applied_at`
- `created_by`
- `source_proposal_ref`
- `governance_decision_ref`
- `track_type`
- `aggregation_key`
- `continuity_level`
- `identity_scope`
- `update_class`
- `applied_identity_influence`
- `previous_identity_state_ref`
- `new_identity_state_ref`
- `supporting_episode_refs`
- `counterevidence_episode_refs`
- `evidence_quality_summary_ref`
- `rollback_plan_ref`
- `supersedes_update_ref`
- `superseded_by_update_ref`
- `active_state`
- `revalidate_if`

---

## 5. Update classes

Suggested update classes:

- `competence_increase`
- `competence_constraint`
- `trust_increase`
- `trust_decrease`
- `preference_update`
- `relationship_memory_update`
- `governance_risk_marker`
- `quarantine_marker`
- `rollback_marker`

Update classes should be typed because not all identity changes have the same risk.

Trust, governance, shared-memory, and system-scope updates should remain stricter than local competence lessons.

---

## 6. Scope binding

Every identity update must declare scope.

Examples:

- individual agent identity;
- relational identity with a specific human or agent;
- shared memory;
- system-level identity policy.

An update must not silently promote:

```text
individual -> relational -> system
```

Any scope promotion must be traceable to governance approval.

---

## 7. Evidence preservation

An identity update must preserve references to both support and counterevidence.

Minimum evidence links:

- source proposal ref;
- source aggregation record ref, if available through proposal;
- supporting episode refs;
- counterevidence episode refs;
- evidence quality summary;
- governance decision reason.

If counterevidence existed at proposal time, it must remain queryable after approval.

---

## 8. Supersession

Identity updates should form an explicit supersession chain.

A new update may:

- supersede an older update;
- narrow an older update;
- broaden an older update only with governance approval;
- deactivate an older update;
- mark an older update as rolled back.

Supersession is not deletion.

---

## 9. Active state

`active_state` should make current identity reconstruction possible.

Suggested values:

- `active`
- `superseded`
- `rolled_back`
- `quarantined`
- `expired`
- `under_review`

Given the ledger, LS should be able to reconstruct active identity influences by selecting updates where `active_state == active` and following supersession / rollback records.

---

## 10. Rollback awareness

Every approved update should include or reference a rollback plan.

Rollback triggers may include:

- new material counterevidence;
- human correction;
- policy change;
- repeated failure after approval;
- evidence channel reclassification;
- consent withdrawal;
- scope inflation detected;
- governance decision superseded.

Rollback should deactivate or supersede the update while preserving the audit trail.

---

## 11. Fail-closed guards

An `IdentityUpdateRecord` should fail closed when:

- `source_proposal_ref` is missing;
- `governance_decision_ref` is missing;
- governance decision is not approving;
- `identity_scope` is missing;
- `update_class` is missing;
- rollback plan is missing;
- counterevidence refs are known but omitted;
- active state cannot be reconstructed;
- update attempts implicit scope promotion.

---

## 12. Relationship to RollbackLedger

`IdentityUpdateRecord` describes the applied influence.

`RollbackLedger` describes later state transitions affecting that influence.

```text
IdentityUpdateRecord(active)
  -> RollbackLedgerEntry(rolled_back | superseded | quarantined | revalidated)
```

Rollback does not erase the update. It changes whether the update remains active.

---

## 13. Summary

`IdentityUpdateRecord` is the governed memory of identity change.

It prevents this collapse:

```text
governance approval == silent permanent mutation
```

and replaces it with:

```text
governed approval -> explicit update record -> rollback-aware ledger
```

Core principle:

> Experience may influence continuity, but every governed identity repositioning must remain auditable and reversible.
