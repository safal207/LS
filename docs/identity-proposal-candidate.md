# IdentityProposalCandidate

## Status

Design note for LS continuity architecture.

This document defines `IdentityProposalCandidate` as the explicit handoff object between track aggregation and governed identity change.

It follows:

- `docs/continuity-coordinator.md`
- `docs/identity-proposal-thresholds.md`
- `schemas/track_aggregation.example.json`
- issue `#717`

---

## 1. Core boundary

`IdentityProposalCandidate` is not an identity update.

```text
TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdate / Reject / Quarantine / Rollback
```

A proposal can request review. It cannot approve itself, apply itself, or mutate stable identity directly.

---

## 2. Why this object exists

Track aggregation can show a pattern, but a pattern is not yet identity.

`IdentityProposalCandidate` exists to preserve the boundary between:

- accumulated experience;
- a proposed identity influence;
- and a governed identity decision.

Without a proposal object, LS risks continuity inflation:

```text
repeated evidence -> implicit identity change
```

This must remain forbidden.

---

## 3. Responsibilities

An `IdentityProposalCandidate` should answer:

- what identity influence is being proposed;
- which aggregation record produced it;
- which episodes support it;
- which counterevidence weakens or blocks it;
- what scope it applies to;
- what confidence state it carries;
- whether governance review is required;
- how it can be rejected, quarantined, superseded, or rolled back.

---

## 4. Non-responsibilities

An `IdentityProposalCandidate` must not:

- verify action outcomes;
- aggregate episodes by itself;
- omit counterevidence;
- promote scope silently;
- approve its own identity effect;
- mutate stable identity;
- erase rollback requirements.

---

## 5. Minimum fields

Candidate fields:

- `proposal_id`
- `proposal_version`
- `created_at`
- `created_by`
- `source_aggregation_record_ref`
- `track_type`
- `aggregation_key`
- `continuity_level`
- `eligible_influence`
- `supporting_episode_refs`
- `counterevidence_episode_refs`
- `confidence_snapshot_ref`
- `evidence_quality_summary`
- `proposed_identity_influence`
- `governance_review_required`
- `governance_reason`
- `rollback_plan_ref`
- `expires_at`
- `revalidate_if`

---

## 6. Proposed identity influence

The proposal should describe the intended identity influence explicitly.

Examples:

- competence confidence increase;
- competence weakness candidate;
- trust repair candidate;
- trust reduction candidate;
- stable preference candidate;
- relational memory update candidate;
- governance-risk quarantine candidate.

The proposal should also specify what it does **not** authorize.

Example:

```text
This proposal may update a local lesson track but must not grant system-level trust authority.
```

---

## 7. Evidence preservation

A proposal must preserve both support and counterevidence.

Minimum evidence summary:

- supporting episode refs;
- failure episode refs, if relevant;
- contradicting episode refs;
- counterevidence episode refs;
- superseded episode refs, if they affected current support count;
- missing or weak evidence notes;
- evidence-channel quality summary.

Counterevidence omission should fail closed.

---

## 8. Scope binding

A proposal must be explicitly scope-bound.

At minimum:

- `continuity_level`: individual / relational / system;
- track family;
- aggregation key;
- affected agent or relationship;
- target scope where relevant.

A proposal must not silently promote:

```text
individual -> relational -> system
```

Any scope promotion should require governance review.

---

## 9. Governance requirement

`governance_review_required` should be true when the proposal affects:

- trust;
- system-level memory;
- shared memory;
- policy behavior;
- high-risk action classes;
- consent or delegation authority;
- identity confidence;
- contradiction-heavy tracks;
- evidence with material uncertainty.

A proposal may be auto-rejected or quarantined before review if required fields are missing.

---

## 10. Rollback and supersession

Every proposal should be rollback-aware.

It should define:

- how an accepted update can be superseded;
- what new evidence triggers revalidation;
- what counterevidence invalidates the proposal;
- whether the proposal expires;
- what prior proposal or update it replaces.

No identity influence should be treated as irreversible by default.

---

## 11. Fail-closed guards

The proposal should fail closed when:

- `source_aggregation_record_ref` is missing;
- supporting evidence is absent;
- counterevidence is known but omitted;
- continuity level is missing;
- scope promotion is implicit;
- rollback plan is missing;
- governance is required but not requested;
- confidence snapshot is missing;
- a single episode tries to become identity update directly.

---

## 12. Relationship to ContinuityCoordinator

ContinuityCoordinator creates or recommends proposals from track state.

It does not approve them.

The coordinator should pass forward:

- track type;
- aggregation key;
- evidence roles;
- counterevidence;
- confidence state;
- threshold result;
- governance requirement.

---

## 13. Relationship to GovernanceDecision

Governance receives an `IdentityProposalCandidate` and may produce a decision such as:

- approve;
- reject;
- quarantine;
- request more evidence;
- supersede;
- rollback.

Governance must preserve the proposal reference so the identity change remains auditable.

---

## 14. Summary

`IdentityProposalCandidate` is the explicit bridge from aggregated continuity to governed identity review.

It prevents this collapse:

```text
track aggregation == identity update
```

Core principle:

> Experience may influence continuity, but only governed continuity may reposition the identity center.
