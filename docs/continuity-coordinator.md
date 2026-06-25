# ContinuityCoordinator

## Status

Design note for LS continuity architecture.

This document defines the **ContinuityCoordinator** as the layer above retained `VerifiedEpisode` records and below governed identity updates.

It follows:

- `docs/verified-episode-prism.md`
- `docs/evidence-channels.md`
- `docs/continuity-vocabulary.md`
- `schemas/verified_episode.example.json`
- issue `#710`

The coordinator answers one question:

> what are multiple retained experiences allowed to mean together?

---

## 1. Core boundary

A `VerifiedEpisode` is an experience candidate, not a stable identity update.

```text
VerifiedEpisode
  -> retained experience
  -> ContinuityCoordinator
  -> track aggregation / counterevidence / confidence shaping
  -> IdentityProposalCandidate
  -> governance review / approval / rollback
```

The coordinator may produce proposals, but it must not silently rewrite stable identity.

---

## 2. Separation of responsibilities

- **OVC** verifies action outcomes.
- **VerifiedEpisode** preserves structured experience.
- **ContinuityCoordinator** aggregates retained experiences into continuity tracks.
- **Governance** decides whether identity proposals are accepted, rejected, rolled back, or quarantined.

The coordinator is not an outcome verifier, raw memory retriever, permission engine, or governance replacement.

---

## 3. Inputs

The coordinator consumes retained episodes and their continuity metadata.

Minimum useful fields:

- `episode_id`
- `episode_outcome_class`
- `evidence_role`
- `retention_status`
- `continuity_level`
- `eligible_influence`
- `identity_update_eligible`
- `expected_transition_ref`
- `patoc_result_ref`
- `observer_independence_basis`
- `evidence_channels`
- `superseded_by`
- `replay_status`
- `lesson_repeat_key`
- `target_ref`
- `actor_ref`

Episodes missing required provenance for their claimed influence level should not receive active continuity influence.

---

## 4. Outputs

Candidate explicit outputs:

- `TrackAggregationRecord`
- `TrackCounterevidenceRecord`
- `TrackConfidenceSnapshot`
- `IdentityProposalCandidate`
- `GovernanceReviewCandidate`

The important property is that aggregation and proposal logic remain inspectable and replayable.

---

## 5. Track families

### `competence_track`

Patterns about repeated ability or inability to perform an action class.

### `trust_track`

Patterns affecting reliability, safety trust, or evidence integrity.

### `relationship_track`

Patterns affecting human-agent or agent-agent continuity: delegation, handoff, consent, trust repair.

### `failure_recovery_track`

Patterns about failure, correction, rollback, and recovery.

### `preference_value_track`

Patterns about durable preferences, delivery style, and human-valued outcomes.

### `governance_risk_track`

Patterns that may require policy, safety, or continuity governance review.

---

## 6. Track routing

For every retained episode, the coordinator should decide:

1. whether it is eligible for aggregation;
2. which track family or families it may contribute to;
3. what aggregation key it belongs under;
4. whether it contributes as `supporting`, `failure`, `contradicting`, or `counterevidence`;
5. whether it is active, superseded, audit-only, or expired.

Candidate routing keys:

- `lesson_repeat_key`
- `action_class`
- `target_ref`
- `actor_ref`
- `relationship_ref`
- `continuity_level`
- `expected_transition_ref`
- `patoc_result_ref`

---

## 7. Aggregation semantics

Aggregation must be provenance-aware.

The coordinator should not simply count episodes. It should account for:

- evidence role;
- outcome class;
- evidence channel quality;
- observer independence;
- freshness;
- supersession;
- contradiction state;
- continuity level;
- governance sensitivity.

### Supporting evidence

`supporting` evidence may increase confidence only when it is active, not superseded, provenance-bound, not replayed, and compatible with the claimed track.

### Failure evidence

`failure` evidence supports failure learning and reliability analysis. It must not be collapsed into successful support just because the failure was verified.

### Contradicting evidence

`contradicting` evidence challenges an expected transition, prior lesson, or current track direction.

### Counterevidence

`counterevidence` is first-class. It may weaken or invalidate an otherwise supported pattern.

---

## 8. Counterevidence behavior

Counterevidence is not passive history.

The coordinator should decide whether counterevidence:

- reduces confidence;
- blocks a proposal;
- invalidates a track snapshot;
- triggers investigation;
- escalates to governance review.

Example: five supporting episodes plus one recent strong contradicting episode should not blindly increase confidence. The result may be a lower confidence snapshot or a review candidate.

---

## 9. Identity proposal boundary

A track may produce an `IdentityProposalCandidate`, but that is not a stable identity update.

```text
TrackAggregationRecord != IdentityUpdate
IdentityProposalCandidate != IdentityUpdate
```

A proposal should contain:

- track family;
- aggregation key;
- supporting episode refs;
- counterevidence refs;
- confidence snapshot;
- proposed influence;
- governance requirements;
- rollback or supersession plan.

---

## 10. Governance boundary

Governance review is required when aggregation may affect:

- system-level continuity;
- trust-sensitive identity;
- high-risk action classes;
- safety / policy behavior;
- cross-agent shared memory;
- memory scope promotion;
- contradiction-heavy tracks.

The coordinator may recommend governance review, but governance remains a separate decision layer.

---

## 11. Required invariants

1. No single `VerifiedEpisode` may directly mutate stable identity.
2. Aggregation must preserve source episode refs and provenance.
3. Counterevidence must be able to weaken, block, or reverse a track.
4. Superseded episodes may remain queryable but must not count as active support.
5. Verified outcome is not identity authority.
6. Governance is separate from aggregation.

---

## 12. Example coordinator pass

```text
Input:
  8 retained episodes under one lesson_repeat_key

Observed:
  6 expected_verified supporting episodes
  1 failed_verified failure episode
  1 unexpected_verified contradicting episode
  no superseded current support
  observer_independence_basis present on 5/6 supporting episodes

Output:
  TrackAggregationRecord(competence_track)
  TrackCounterevidenceRecord(unexpected_verified episode)
  TrackConfidenceSnapshot(confidence = moderate, not high)
  no direct identity update
  lesson_candidate allowed
  identity_proposal_candidate blocked until counterevidence review
```

---

## 13. Summary

ContinuityCoordinator turns retained episodes into continuity patterns without allowing any episode to self-authorize identity change.

Core principle:

> Experience may influence continuity, but only governed continuity may reposition the identity center.
