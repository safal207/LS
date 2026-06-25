# IdentitySnapshot

## Status

Design note for LS continuity architecture.

This document defines `IdentitySnapshot` as the reconstructed, point-in-time view of an agent's active identity state.

It follows:

- `docs/identity-update-record.md`
- `docs/rollback-ledger.md`
- `docs/governance-handoff.md`
- `schemas/identity_update_record.example.json`
- issue `#727`

---

## 1. Core boundary

An identity snapshot is not a proposal, decision, or update record.

```text
IdentityUpdateRecord + RollbackLedger
  -> IdentitySnapshot
```

`IdentitySnapshot` is the materialized current view of identity reconstructed from governed identity records and rollback history.

---

## 2. Why this object exists

LS can now store:

- verified episodes;
- track aggregations;
- identity proposals;
- governance decisions;
- approved identity updates;
- rollback / supersession transitions.

But a system that only stores changes still needs a formal answer to the practical question:

> **Who is this agent right now?**

`IdentitySnapshot` exists to answer that question without losing provenance, scope, rollback history, or quarantine state.

---

## 3. Responsibilities

An `IdentitySnapshot` should answer:

- which identity influences are currently active;
- which trust / competence / preference / relationship markers are live;
- which updates were superseded, rolled back, quarantined, or expired;
- which scope each active identity influence belongs to;
- what provenance justifies the current active state;
- what the identity looked like at a chosen time.

---

## 4. Non-responsibilities

An `IdentitySnapshot` must not:

- approve anything;
- create new identity influence by itself;
- ignore rollback or supersession state;
- silently promote scope;
- erase history;
- mutate the ledger while reconstructing the current state.

It is a read model, not a governance actor.

---

## 5. Snapshot composition

A snapshot should be reconstructed from:

- active `IdentityUpdateRecord` objects;
- rollback ledger entries;
- supersession links;
- quarantine markers;
- point-in-time filters;
- scope filters where needed.

This means the snapshot is **derived**, not hand-written.

---

## 6. Minimum sections

Candidate top-level sections:

- `snapshot_id`
- `snapshot_time`
- `snapshot_scope`
- `reconstruction_basis`
- `active_identity_influences`
- `quarantined_influences`
- `recent_rollbacks`
- `recent_supersessions`
- `provenance_summary`
- `warnings`

---

## 7. Active identity influences

The core of the snapshot is the set of active influences that currently shape the agent.

Examples:

- active competence-confidence updates;
- active competence constraints;
- active trust increases / decreases;
- active preference updates;
- active relationship-memory markers;
- active governance-risk markers.

Each active influence should remain linked to:

- the identity update that introduced it;
- the proposal and governance decision behind it;
- its scope and update class.

---

## 8. Scope preservation

Identity must remain scope-bound inside the snapshot.

Suggested scopes:

- `individual`
- `relational`
- `shared_memory`
- `system`

A snapshot should be able to distinguish:

- what is true about the agent in general;
- what is only true in relation to a specific human or agent;
- what affects shared memory;
- what affects system-level policy or trust.

---

## 9. Inactive and non-active states

A snapshot should **not** treat every historical update as active identity.

It must exclude or separate:

- rolled-back updates;
- superseded updates;
- expired updates;
- quarantined updates;
- under-review updates that never became active.

These may still appear in summary sections, but not as active identity influences.

---

## 10. Point-in-time reconstruction

`IdentitySnapshot` should support both:

- **current snapshot** — active identity now;
- **historical snapshot** — active identity at time `T`.

This means reconstruction must respect:

- update timestamps;
- rollback / supersession timestamps;
- expiration windows;
- scope-specific time filters if later needed.

---

## 11. Explainability requirement

Every active identity influence in the snapshot should be explainable.

At minimum, LS should be able to answer:

- which `IdentityUpdateRecord` made this active;
- which `GovernanceDecision` approved it;
- which proposal requested it;
- what evidence and counterevidence existed at approval time;
- whether any rollback risk remains open.

If a snapshot cannot explain why an active influence exists, that is a reconstruction failure.

---

## 12. Example view of a snapshot

A snapshot may eventually materialize something like:

### Competence
- publish-doc workflow: moderate confidence
- governance-contract reasoning: strong confidence

### Trust
- no system-level trust elevation active
- bounded local trust for GitHub governance workflow

### Preferences
- prefers fail-closed review and explicit evidence preservation

### Relationship memory
- Alex-specific continuity active
- LS architecture continuity active

### Quarantine / review
- one unresolved trust proposal under review

### Recent rollback history
- one older competence update superseded

This is only an illustrative view, not the canonical schema.

---

## 13. Fail-closed expectations

Snapshot reconstruction should fail closed when:

- active state cannot be determined from update + rollback history;
- a supposedly active influence has been rolled back or superseded;
- scope is missing;
- provenance chain is broken;
- reconstruction would require guessing between contradictory states.

When reconstruction fails, LS should surface uncertainty instead of silently fabricating a stable identity view.

---

## 14. Relationship to future UI / product layers

`IdentitySnapshot` is the likely foundation for:

- a “Who is this agent now?” dashboard;
- human review interfaces for identity state;
- diff views between two points in time;
- relational snapshots per user or team;
- multi-agent continuity views.

It is the first layer that turns identity history into a usable present-tense model.

---

## 15. Summary

`IdentitySnapshot` is the reconstructed present-tense identity of the agent.

It prevents this collapse:

```text
identity ledger == current identity by default
```

and replaces it with:

```text
governed identity ledger -> explicit reconstruction -> current active identity view
```

Core principle:

> Experience may influence continuity, governed continuity may reposition the identity center, and the resulting identity center must remain reconstructable, explainable, and reviewable at any point in time.
