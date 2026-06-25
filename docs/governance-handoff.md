# Governance Handoff

## Status

Design note for LS continuity architecture.

This document defines how an `IdentityProposalCandidate` moves from continuity aggregation into governance review, and what must remain preserved across that handoff.

It follows:

- `docs/continuity-coordinator.md`
- `docs/identity-proposal-candidate.md`
- `docs/identity-proposal-thresholds.md`
- `schemas/track_aggregation.example.json`
- `schemas/identity_proposal_candidate.example.json`
- issue `#717`

---

## 1. Core boundary

Continuity aggregation may propose. Governance decides.

```text
VerifiedEpisode
  -> TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdate / Reject / Quarantine / Rollback / RequestMoreEvidence
```

No continuity artifact may approve itself.

---

## 2. Purpose of handoff

The governance handoff exists to prevent this collapse:

```text
aggregated pattern == approved identity change
```

The handoff makes identity influence explicit, reviewable, reversible, and auditable.

Governance is the point where LS decides whether a proposal should:

- change stable identity;
- remain only a lesson or local memory;
- be quarantined;
- be rejected;
- be rolled back later;
- or require more evidence first.

---

## 3. Handoff inputs

Governance should receive an `IdentityProposalCandidate` plus the minimal references needed to inspect its basis.

Required inputs:

- proposal object;
- source aggregation record reference;
- supporting episode refs;
- counterevidence refs;
- confidence snapshot;
- evidence quality summary;
- continuity level;
- rollback / supersession plan;
- any linked governance-risk flags.

If these are missing, the proposal should fail closed before review.

---

## 4. Handoff invariants

### 4.1 Proposal is not update

```text
IdentityProposalCandidate != IdentityUpdate
```

Governance must produce an explicit decision before any identity update may occur.

### 4.2 Counterevidence must survive handoff

A proposal cannot strip away contradicting or failure evidence before review.

### 4.3 Scope must survive handoff

Governance must know whether the proposal is:

- individual;
- relational;
- system;
- shared-memory scoped.

### 4.4 Review outcome must remain linked to proposal provenance

An approved or rejected decision must preserve the proposal reference and its evidence basis.

### 4.5 Rollback must remain possible

If governance approves a proposal, the resulting update must still remain supersedable or reversible under later evidence.

---

## 5. Governance decision classes

Governance should support at least these result classes for identity proposals.

### `approve`

The proposal is accepted for identity influence.

Effects may include:

- create or update stable identity state;
- create a governed trust or preference update;
- create a review trail and rollback reference.

### `reject`

The proposal is denied.

Typical reasons:

- insufficient support;
- material contradiction;
- missing scope binding;
- missing rollback plan;
- confidence too low;
- evidence quality too weak.

### `quarantine`

The proposal is retained but blocked from identity mutation until a risk or contradiction is resolved.

Typical reasons:

- possible memory laundering;
- suspected scope inflation;
- conflict between evidence channels;
- unresolved trust-risk pattern.

### `request_more_evidence`

The proposal is not approved or rejected yet, but governance requires more episodes, more independent observation, or better evidence quality.

### `rollback`

A previously approved identity influence is actively reversed or superseded due to new evidence, contradiction, human correction, or policy change.

---

## 6. Minimum governance review questions

Governance should be able to answer at least these questions:

1. **What identity influence is being proposed?**
2. **What aggregation record produced it?**
3. **How many trusted supporting episodes exist?**
4. **What counterevidence exists and how recent is it?**
5. **What continuity level is affected?**
6. **Would approval change trust, delegation, consent, or shared memory?**
7. **Is governance review mandatory for this track family?**
8. **How would the resulting identity influence be rolled back or superseded?**

If the answer to these questions is missing or ambiguous, governance should prefer reject, quarantine, or request-more-evidence over approval.

---

## 7. Proposal states before governance

An `IdentityProposalCandidate` may arrive in one of several pre-review states.

### `blocked_pre_review`

The proposal object exists, but known evidence problems already block active review.

Examples:

- material counterevidence already blocks threshold;
- confidence snapshot missing;
- source aggregation record missing;
- implicit scope promotion;
- rollback plan missing.

### `reviewable`

The proposal has enough structure and evidence quality to enter governance review.

### `quarantine_recommended`

The proposal should be preserved, but continuity/governance risk is high enough that quarantine is the safest default.

---

## 8. What governance must preserve

When governance receives a proposal, it should preserve at least:

- `proposal_id`
- `source_aggregation_record_ref`
- `track_type`
- `aggregation_key`
- `continuity_level`
- `supporting_episode_refs`
- `counterevidence_episode_refs`
- `confidence_snapshot`
- `evidence_quality_summary`
- `governance_reason`
- `rollback_plan_ref`
- final decision and decision timestamp

This keeps identity changes auditable and reversible.

---

## 9. Approval requirements

Governance should not approve identity influence when any of the following remain unresolved:

- known material counterevidence;
- missing source aggregation record;
- missing confidence snapshot;
- missing rollback or supersession path;
- implicit scope promotion;
- single-episode direct promotion attempt;
- evidence-channel contradiction with no resolution;
- trust/system-level effect without review.

---

## 10. Rejection vs quarantine

Use **reject** when the proposal itself is unsound or unsupported.

Use **quarantine** when the proposal may be important, but acting on it would be unsafe before more review.

Examples:

### Reject

- two weak supporting episodes and one strong contradiction;
- no rollback plan;
- proposal tries to mutate system identity from local evidence.

### Quarantine

- evidence suggests a serious trust rupture but provenance is incomplete;
- repeated contradiction cluster indicates possible manipulation or memory laundering;
- a shared-memory proposal could affect multiple agents and needs deeper review.

---

## 11. Rollback path

Every approved identity influence should keep a rollback path.

Minimum rollback links:

- proposal ref;
- approval decision ref;
- resulting identity update ref;
- rollback trigger conditions;
- superseding proposal or evidence refs if later replaced.

Rollback triggers may include:

- new contradiction;
- human correction;
- policy change;
- repeated failure;
- evidence reclassification;
- consent withdrawal.

---

## 12. Example handoff flow

### Step 1 — track aggregation

ContinuityCoordinator aggregates repeated competence episodes for a publishing workflow.

### Step 2 — threshold check

The track meets lesson threshold but not identity threshold because recent counterevidence remains material.

### Step 3 — proposal object

LS still creates an `IdentityProposalCandidate` specimen with:

- supporting refs;
- counterevidence refs;
- confidence snapshot;
- explicit note that identity promotion is currently blocked.

### Step 4 — governance handoff

Governance receives the proposal and sees:

```text
reviewable = false
recommended_decision = do_not_promote_to_identity_update
```

### Step 5 — governance outcome

Governance may choose:

- reject;
- request more evidence;
- quarantine if the contradiction pattern looks risky.

---

## 13. Summary

Governance handoff is the membrane between continuity and identity authority.

It ensures that:

- track aggregation does not silently become identity mutation;
- counterevidence survives into review;
- scope remains explicit;
- rollback remains possible;
- approval is a separate governed act.

Core principle:

> Experience may influence continuity, but only governed continuity may reposition the identity center.
