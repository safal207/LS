# IdentityProposalCandidate

## Status

Design note for LS continuity and identity-governance architecture.

This document defines `IdentityProposalCandidate` as the explicit, fail-closed handoff object between continuity-track aggregation and governed identity change.

It follows:

- `docs/continuity-coordinator.md`
- `docs/identity-proposal-thresholds.md`
- `docs/continuity-vocabulary.md`
- `schemas/track_aggregation.example.json`
- the Trusted Runtime identity proposal, approval, application, invalidation, expiry, and rollback contracts
- issue `#717`

---

## 1. Core boundary

```text
TrackAggregationRecord
  -> IdentityProposalCandidate
  -> governance intake
  -> IdentityUpdateProposal / Reject / Quarantine / MoreEvidence
  -> approval / patch / commit / application / rollback
```

`IdentityProposalCandidate` is not an identity update, approval, patch, active profile, authorization decision, or runtime permission.

```text
IdentityProposalCandidate != IdentityUpdate
IdentityProposalCandidate != IdentityUpdateApproval
IdentityProposalCandidate != IdentityProfilePatch
```

A candidate can request review. It cannot approve itself, apply itself, or mutate stable identity directly.

---

## 2. Why this object exists

Track aggregation can show a pattern, but a pattern is not yet identity.

`IdentityProposalCandidate` preserves the boundary between:

- accumulated experience;
- an inspectable proposed identity influence;
- and a governed identity decision.

Without a proposal object, LS risks continuity inflation:

```text
repeated evidence -> implicit identity change
```

This must remain forbidden.

---

## 3. Relationship to existing Trusted Runtime contracts

The current Trusted Runtime already contains a review-only `IdentityUpdateProposal` and a separated governance lifecycle:

```text
IdentityUpdateProposal
  -> IdentityUpdateApproval
  -> IdentityProfilePatch
  -> IdentityPatchCommit
  -> IdentityApplication
  -> optional IdentityRollback
```

`IdentityProposalCandidate` does not replace that stack.

It is the continuity-side handoff object immediately before the runtime proposal contract.

A conforming adapter may convert a ready candidate into the existing `IdentityUpdateProposal`, but only when:

- all required candidate fields are present;
- the source aggregation is bound by reference and digest;
- support, failure, contradiction, and counterevidence remain distinguishable;
- continuity scope is unchanged;
- governance requirements are preserved;
- expiry, revalidation, and rollback semantics are explicit;
- no approval, application, patch, or profile activation is inferred.

Until such an adapter exists, the example artifact is descriptive and must not be treated as a runtime identity mutation command.

---

## 4. Responsibilities

An `IdentityProposalCandidate` should answer:

- what identity influence is being proposed;
- which aggregation record produced it;
- which episodes support it;
- which failures remain relevant;
- which contradiction or counterevidence weakens or blocks it;
- what scope it applies to;
- what confidence state and evidence quality it carries;
- whether governance review is required;
- how it can expire, be rejected, quarantined, superseded, revalidated, or rolled back.

---

## 5. Non-responsibilities

An `IdentityProposalCandidate` must not:

- verify action outcomes;
- aggregate episodes by itself;
- infer traits from free-form prose;
- omit counterevidence;
- collapse verified failure into successful support;
- promote scope silently;
- approve its own identity effect;
- mutate stable identity;
- grant tool, execution, access, delegation, or policy authority;
- erase rollback requirements.

---

## 6. Minimum fields

### Identity and provenance

- `proposal_id`
- `proposal_version`
- `created_at`
- `created_by`
- `source_aggregation_record_ref`
- `source_aggregation_digest`

### Track and scope

- `track_type`
- `aggregation_key`
- `continuity_level`
- `actor_ref`
- `target_scope`
- `scope_constraints`

### Evidence

- `supporting_episode_refs`
- `failure_episode_refs`
- `contradicting_episode_refs`
- `counterevidence_episode_refs`
- `superseded_episode_refs`
- `confidence_snapshot_ref`
- `evidence_quality_summary`

### Proposed influence

- `eligible_influence`
- `proposed_identity_influence`

### Governance and lifecycle

- `governance_review_required`
- `governance_reason`
- `rollback_plan_ref`
- `expires_at`
- `revalidate_if`
- `candidate_state`

### Authority boundary

- `authority_effects`

All authority-effect values must remain false at candidate creation.

A missing source aggregation reference or digest is a fail-closed error.

---

## 7. Candidate states

Suggested states:

- `READY_FOR_GOVERNANCE` — complete candidate eligible for governance intake;
- `MORE_EVIDENCE_REQUIRED` — meaningful pattern, insufficient evidence;
- `BLOCKED_BY_COUNTEREVIDENCE` — material contradiction prevents promotion;
- `QUARANTINED` — malformed, scope-inflating, provenance-weak, or policy-sensitive candidate;
- `EXPIRED` — candidate requires revalidation before further review;
- `SUPERSEDED` — a later candidate or aggregation replaces it.

A candidate in any state other than `READY_FOR_GOVERNANCE` must not be adapted into an active runtime proposal.

---

## 8. Proposed identity influence

The intended influence should be bounded and machine-inspectable.

Recommended shape:

```json
{
  "operation": "SET_TRAIT_CANDIDATE",
  "trait_key": "working_tendencies.test_before_claim",
  "proposed_value": true,
  "scope": "individual",
  "reason": "Repeated trusted evidence supports an evidence-first working tendency."
}
```

The candidate must not contain an already-applied profile patch or imply that a trait is active.

Free-form explanatory prose may accompany the structured influence, but prose alone is not sufficient for runtime governance.

---

## 9. Evidence preservation

A proposal must preserve both support and counterevidence.

Minimum evidence summary:

- supporting episode refs;
- failure episode refs, if relevant;
- contradicting episode refs;
- counterevidence episode refs;
- superseded episode refs, if they affected current support count;
- missing or weak evidence notes;
- evidence-channel quality summary.

The candidate must not:

- omit known contradicting episodes;
- remove counterevidence because support remains above threshold;
- summarize conflicting evidence into one unsupported confidence number;
- treat superseded support as current support;
- use duplicate refs to amplify confidence or counts.

Counterevidence omission must fail closed.

---

## 10. Scope binding

A proposal must be explicitly scope-bound.

At minimum:

- `continuity_level`: `individual`, `relational`, or `system`;
- track family;
- aggregation key;
- affected agent or relationship;
- target scope where relevant.

A proposal must not silently promote:

```text
individual -> relational -> system
```

Examples:

- a preference confirmed with one human must not become a global preference;
- project-local competence must not become system-wide competence;
- relationship trust must not grant execution authority;
- local failure must not become permanent incapability.

Any scope promotion requires explicit justification and governance review.

---

## 11. Governance requirement

`governance_review_required` must be true when the proposal affects or may affect:

- trust;
- system-level or shared memory;
- policy or safety behavior;
- high-risk action classes;
- consent or delegation boundaries;
- durable capability or incapability claims;
- identity confidence;
- contradiction-heavy tracks;
- evidence with material uncertainty;
- continuity-scope expansion.

A proposal may be rejected or quarantined before review if required fields are missing.

Even when review is not mandatory for a low-risk local candidate, application remains a separate governed operation.

---

## 12. Rollback, expiry, and supersession

Every proposal must be rollback-aware.

It should define:

- how an accepted update can be removed or superseded;
- what new evidence triggers revalidation;
- what counterevidence invalidates the proposal;
- whether and when the proposal expires;
- what prior proposal or update it replaces;
- which source records remain available for replay.

Typical revalidation triggers:

- new material counterevidence;
- confidence drop;
- human correction;
- policy change;
- relationship-scope change;
- source aggregation supersession;
- source episode expiry or redaction;
- attempted scope expansion.

No identity influence should be treated as irreversible by default.

---

## 13. Fail-closed invariants

1. One episode cannot create a ready identity candidate.
2. Missing source aggregation reference or digest blocks the candidate.
3. Counterevidence cannot be omitted.
4. Duplicate evidence refs cannot amplify confidence or support.
5. Candidate scope cannot exceed source aggregation scope.
6. Blocked, quarantined, expired, or superseded candidates cannot be applied.
7. The proposing actor cannot approve its own candidate.
8. Candidate creation cannot produce a patch, application, active profile, tool permission, or execution authorization.
9. Every accepted influence must remain reversible or supersedable.
10. Governance remains separate from continuity aggregation.

---

## 14. Compatibility mapping

A future adapter into the existing Trusted Runtime `IdentityUpdateProposal` should map conservatively:

| Candidate field | Existing runtime proposal field or handling |
|---|---|
| `proposal_id` | `proposal_id` |
| `target_scope` / `continuity_level` | bounded `scope` plus typed metadata |
| `aggregation_key` | `repeat_key` or canonical aggregation key |
| structured proposed influence | `candidate_statement` plus structured metadata until a typed patch-candidate contract exists |
| supporting refs | `supporting_episode_refs` |
| failure / contradiction / counterevidence refs | `evidence_refs` plus mandatory typed metadata; no silent dropping |
| confidence snapshot | `aggregated_confidence` plus source snapshot ref |
| governance requirement | `approval_required=true`; reason preserved in metadata |
| expiry / revalidation | preserved in metadata until first-class fields exist |
| rollback plan | preserved and validated before patch creation |

The adapter must fail closed when the current runtime schema cannot preserve a candidate invariant.

---

## 15. Relationship to ContinuityCoordinator

ContinuityCoordinator creates or recommends candidates from track state.

It does not approve them.

The coordinator passes forward:

- track type and aggregation key;
- source aggregation reference and digest;
- evidence roles and lifecycle states;
- counterevidence;
- confidence state;
- threshold result;
- continuity scope;
- governance requirement.

---

## 16. Relationship to governance

Governance receives a candidate and may:

- accept it for runtime proposal construction;
- reject it;
- quarantine it;
- request more evidence;
- mark it expired;
- supersede it;
- later rollback an applied influence through the existing governance stack.

Governance must preserve the candidate and source aggregation references so the lifecycle remains auditable and replayable.

---

## 17. Summary

`IdentityProposalCandidate` is the explicit bridge from aggregated continuity to governed identity review.

It prevents this collapse:

```text
track aggregation == identity update
```

> Experience may influence continuity, but only governed continuity may reposition the identity center.
