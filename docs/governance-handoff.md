# Governance handoff for identity proposal candidates

## Status

Design note for LS continuity and identity-governance architecture.

This document defines how an `IdentityProposalCandidate` moves from continuity interpretation into the existing Trusted Runtime identity-governance lifecycle.

It follows:

- `docs/continuity-coordinator.md`
- `docs/identity-proposal-thresholds.md`
- `docs/identity-proposal-candidate.md`
- `schemas/identity_proposal_candidate.example.json`
- the Trusted Runtime `IdentityUpdateProposal`, approval, patch, commit, application, and rollback contracts
- issue `#717`

---

## 1. Core boundary

```text
TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceIntakeDecision
  -> optional IdentityUpdateProposal construction
  -> IdentityUpdateApproval
  -> IdentityProfilePatch
  -> IdentityPatchCommit
  -> IdentityApplication
  -> optional IdentityRollback
```

The handoff is a boundary, not a shortcut.

A candidate cannot:

- approve itself;
- create a profile patch directly;
- activate identity;
- grant authority;
- bypass expiry, contradiction, or provenance checks.

---

## 2. Governance intake outcomes

Governance intake should produce one explicit outcome.

### `ACCEPT_FOR_REVIEW`

The candidate is complete enough to construct or bind a runtime review-only proposal.

This does not approve or apply the identity influence.

### `REJECT`

The candidate is structurally or semantically ineligible.

Typical reasons:

- missing provenance;
- missing source aggregation digest;
- impossible or forbidden scope;
- known counterevidence omitted;
- authority-bearing effect requested;
- direct identity mutation attempted.

### `QUARANTINE`

The candidate requires investigation before it can be trusted.

Typical reasons:

- suspected memory laundering;
- unexplained scope inflation;
- conflicting evidence-channel claims;
- malformed provenance chain;
- self-authored trust claim;
- governance-risk track escalation.

### `REQUEST_MORE_EVIDENCE`

The candidate shape is valid, but evidence is insufficient or materially contradicted.

### `EXPIRE`

The candidate is outside its review window and requires revalidation.

### `SUPERSEDE`

A newer aggregation or candidate replaces the current one.

The superseded candidate remains queryable for audit and replay.

---

## 3. Required intake checks

Governance must validate at least the following before accepting a candidate for review.

### A. Identity and source binding

- `proposal_id` is present and stable;
- `source_aggregation_record_ref` is present;
- `source_aggregation_digest` is present and matches the referenced aggregation;
- the aggregation exists and is inspectable;
- candidate creation is not based directly on a single episode.

### B. Evidence preservation

- supporting refs match the source aggregation;
- failure refs remain separate from support;
- contradicting refs are preserved;
- counterevidence refs are preserved;
- superseded and expired support is not counted as current;
- duplicate refs do not amplify support or confidence;
- confidence snapshot and evidence-quality summary remain traceable.

### C. Scope preservation

- candidate continuity level does not exceed source aggregation continuity level;
- actor, relationship, project, and target scope remain bound;
- requested scope expansion is explicit and separately reviewable;
- relational evidence is not promoted to global identity;
- local failure is not promoted to permanent incapability.

### D. Lifecycle readiness

- candidate is not expired or superseded;
- rollback plan is present;
- revalidation triggers are present;
- known invalidation conditions are not currently true;
- candidate state is `READY_FOR_GOVERNANCE`.

### E. Authority boundary

All candidate authority effects must be false.

The candidate must not grant:

- execution authorization;
- tool access;
- policy bypass;
- delegation authority;
- approval authority;
- profile mutation authority;
- continuity-scope expansion authority.

---

## 4. Preservation envelope

The governance handoff must preserve a minimum envelope even when adapting into the existing runtime `IdentityUpdateProposal` contract.

Required preserved data:

- candidate reference and digest;
- source aggregation reference and digest;
- track type;
- aggregation key;
- continuity level;
- actor and target scope;
- supporting refs;
- failure refs;
- contradicting refs;
- counterevidence refs;
- superseded refs affecting current counts;
- confidence snapshot reference;
- evidence-quality summary;
- structured proposed identity influence;
- governance reason;
- expiry;
- revalidation triggers;
- rollback plan;
- all-false authority effects.

If the receiving runtime schema cannot preserve one of these invariants directly, the handoff must either:

1. preserve it in typed metadata validated by policy; or
2. fail closed and reject the conversion.

Silent field loss is forbidden.

---

## 5. Conservative adapter to the current runtime proposal

The current Trusted Runtime `IdentityUpdateProposal` is review-only and already enforces:

- `approval_required=true`;
- `approval_state=PENDING`;
- `applied=false`;
- `application_ref=null`.

A candidate-to-runtime adapter should additionally enforce:

- candidate state is `READY_FOR_GOVERNANCE`;
- source aggregation reference and digest are preserved;
- counterevidence is absent only when the source aggregation confirms none exists;
- no scope promotion occurs;
- proposed influence is represented structurally in metadata until a first-class typed runtime field exists;
- expiry and rollback information are preserved;
- proposer identity is preserved for later self-approval checks.

Suggested conservative mapping:

| Candidate | Runtime proposal |
|---|---|
| `proposal_id` | `proposal_id` |
| `target_scope` | `scope` |
| `aggregation_key` | `repeat_key` |
| proposed influence summary | `candidate_statement` |
| supporting refs | `supporting_episode_refs` |
| full typed evidence refs | `evidence_refs` and typed metadata |
| confidence value | `aggregated_confidence` |
| governance requirement | `approval_required=true` |
| candidate/source bindings | metadata |
| expiry/revalidation/rollback | metadata pending first-class fields |

The adapter must not fabricate support count, confidence, evidence quality, or missing counterevidence state.

---

## 6. Decision binding

Every governance decision must bind to the exact candidate and proposal material reviewed.

Minimum decision bindings:

- candidate ID;
- candidate digest;
- source aggregation digest;
- runtime proposal ID and digest, if constructed;
- decision actor;
- proposing actor;
- decision time;
- decision reason;
- evidence and contradiction refs considered;
- expiry window where applicable.

The proposing actor must not approve its own identity influence.

A later change to the candidate, source aggregation, evidence set, proposed influence, scope, or rollback plan invalidates the prior review binding.

---

## 7. Counterevidence after handoff

New material counterevidence may arrive after governance intake.

Required handling:

- before approval: block or invalidate the pending proposal;
- after approval but before application: invalidate the approval window;
- after application: create an explicit revalidation, supersession, or rollback path;
- during replay: rebuild the same lifecycle outcome without reapplying side effects.

Counterevidence must never be appended as passive history while the affected identity influence remains silently active.

---

## 8. Expiry and revalidation

Expiry does not delete history.

An expired candidate or approval:

- remains queryable;
- cannot create a new patch;
- cannot activate a profile;
- requires a fresh evidence and scope check;
- should produce a new candidate or decision reference when revalidated.

Typical revalidation triggers:

- new material counterevidence;
- human correction;
- confidence drop;
- policy change;
- source aggregation supersession;
- relationship or target-scope change;
- capability recovery or constraint expiry;
- attempted scope expansion.

---

## 9. Rollback relationship

The candidate carries rollback intent; the existing governance stack performs rollback.

The candidate must identify what would invalidate or reverse the proposed influence.

The runtime rollback lifecycle must:

- preserve the applied profile version;
- create a new profile version rather than deleting history;
- bind rollback to the application being reversed;
- retain the candidate, proposal, approval, patch, commit, application, and rollback chain;
- avoid replay-driven duplicate rollback or application.

---

## 10. Fail-closed matrix

| Condition | Intake outcome |
|---|---|
| candidate state is ready, complete, uncontradicted, scope-bound | `ACCEPT_FOR_REVIEW` |
| evidence is insufficient but structurally valid | `REQUEST_MORE_EVIDENCE` |
| material counterevidence blocks eligibility | `REQUEST_MORE_EVIDENCE` or `QUARANTINE` |
| source aggregation ref or digest missing | `REJECT` |
| known counterevidence omitted | `REJECT` |
| implicit scope promotion | `QUARANTINE` |
| authority effect is true | `REJECT` |
| candidate expired | `EXPIRE` |
| newer candidate replaces it | `SUPERSEDE` |
| proposer attempts self-approval | `REJECT` |
| receiving schema would silently lose required invariants | `REJECT` |

---

## 11. Replay and audit

Governance handoff must be replayable without rerunning models or reapplying identity changes.

Replay should reconstruct:

- candidate intake outcome;
- runtime proposal construction, if any;
- decision binding;
- approval validity;
- patch and commit references;
- application state;
- supersession, invalidation, expiry, and rollback state.

Missing, duplicated, reordered, mismatched, or tampered records must fail closed.

---

## 12. Summary

The governance handoff preserves the semantic distance between:

```text
an aggregated pattern
and
an applied identity change
```

A candidate may enter review only when its provenance, scope, counterevidence, lifecycle, rollback, and authority boundaries survive intact.

> A proposal may ask governance to reposition identity, but it may never reposition identity by itself.
