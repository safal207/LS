# Identity Proposal Thresholds

## Status

Design note for LS continuity architecture.

This document defines when aggregated continuity tracks may become identity proposal candidates, and when they must remain local lessons, history-only records, or governance-review candidates.

It follows:

- `docs/continuity-coordinator.md`
- `docs/continuity-vocabulary.md`
- `docs/verified-episode-prism.md`
- `docs/evidence-channels.md`
- `schemas/verified_episode.example.json`
- `schemas/track_aggregation.example.json`
- issue `#710`

---

## 1. Core boundary

Identity proposal is not identity update.

```text
TrackAggregationRecord != IdentityUpdate
IdentityProposalCandidate != IdentityUpdate
```

A proposal only means that an aggregated pattern may be reviewed as possible identity influence.

Stable identity may change only after governed review, approval, and rollback-aware application.

---

## 2. Default fail-closed rule

If threshold information is incomplete, ambiguous, or contradictory, LS should choose the safer lower influence level.

Default fallback:

```text
history_only or lesson_candidate, not identity_proposal_candidate
```

No single `VerifiedEpisode` may directly produce a stable identity update.

---

## 3. Minimum threshold dimensions

A track may be considered for identity proposal only when these dimensions are explicit:

1. **track family** — which continuity track is affected;
2. **aggregation key** — what repeated pattern is being aggregated;
3. **trusted support** — how many active, non-superseded supporting episodes exist;
4. **counterevidence** — what failure, contradiction, or counterevidence exists;
5. **evidence quality** — whether required evidence channels and independence basis are present;
6. **continuity level** — individual, relational, or system;
7. **governance sensitivity** — whether the proposal touches trust, safety, policy, or shared memory;
8. **rollback plan** — how an accepted identity influence can be revised or removed later.

---

## 4. Influence levels

### `history_only`

Use when the episode or aggregation remains useful for audit or context but should not influence learning or identity.

Typical reasons:

- superseded records;
- weak evidence;
- unresolved contradiction;
- missing expected-transition provenance;
- missing observer independence basis.

### `lesson_candidate`

Use when evidence is useful for local learning but not strong enough for identity proposal.

Typical reasons:

- single verified episode;
- small number of repeated episodes;
- local failure learning;
- expected outcome verified but not repeated enough;
- counterevidence present but not severe.

### `shared_memory_candidate`

Use when a pattern may matter to multiple agents or human-agent relation, but should not yet change stable identity.

Typical reasons:

- repeated handoff behavior;
- repeated delegation quality;
- repeated user confirmation;
- relationship-scoped pattern.

### `identity_proposal_candidate`

Use only when an aggregated pattern is stable enough to be reviewed as identity influence.

This requires repeated trusted support, clear scope, low unresolved counterevidence, and a rollback-aware proposal.

### `governance_review_candidate`

Use when the pattern is sensitive, risky, contradictory, system-scoped, or could affect policy / trust / shared memory.

Governance review may approve, reject, quarantine, or request more evidence.

---

## 5. Suggested baseline thresholds

These are initial conservative defaults, not final runtime constants.

| Track family | Minimum for lesson | Minimum for identity proposal | Governance review required? |
|---|---:|---:|---|
| `competence_track` | 1 trusted episode | 3+ trusted supporting episodes with no material counterevidence | if system/high-risk |
| `trust_track` | 1 relevant episode | 3+ consistent trusted episodes | usually yes |
| `relationship_track` | 1 relational episode | 3+ repeated relational confirmations | if trust/consent-impacting |
| `failure_recovery_track` | 1 verified failure/recovery | repeated failure + verified recovery pattern | if safety-sensitive |
| `preference_value_track` | 1 human confirmation | repeated human confirmations across time | if durable preference update |
| `governance_risk_track` | 1 risk signal | identity proposal usually blocked | yes |

Important: these counts are not enough by themselves. Evidence quality and counterevidence can block promotion.

---

## 6. Evidence quality requirements

For identity proposal candidacy, supporting episodes should normally be:

- active;
- not superseded;
- not replay-only;
- expected-transition bound;
- supported by typed evidence channels;
- carrying `observer_independence_basis` where independence is claimed;
- free of unresolved channel contradiction;
- within the same aggregation scope.

Weak or self-authored-only evidence may support investigation or local context, but should not support identity proposal.

---

## 7. Counterevidence gates

Counterevidence must actively shape threshold decisions.

A track should not become identity-proposal-eligible when:

- recent material contradiction exists;
- a supporting episode is superseded;
- expected outcome and unexpected outcome are collapsed;
- failure evidence is treated as success;
- actor assertion is the only evidence;
- runtime receipt is the only evidence for identity influence;
- evidence channels are dependent but counted as independent.

Counterevidence may:

- reduce confidence;
- stall promotion;
- block identity proposal;
- trigger governance review;
- force history-only retention.

---

## 8. Track-specific rules

### 8.1 `competence_track`

May propose identity influence only after repeated trusted success or repeated verified failure pattern.

Must block proposal when:

- material contradicting episode is recent;
- trusted support count is below threshold;
- target-state verification is missing;
- expected transition provenance is missing.

### 8.2 `trust_track`

Trust changes are stricter than local lessons.

A trust proposal usually requires governance review because trust affects future authorization and delegation.

Must block or review when:

- evidence is self-authored;
- observer independence is missing;
- contradiction density is high;
- memory laundering or scope inflation is suspected.

### 8.3 `relationship_track`

Relational proposals require relational evidence.

Human confirmation or relational counterparty evidence may matter strongly, but should remain typed separately from target-state verification.

Must review when:

- consent is affected;
- delegation authority changes;
- relationship memory becomes shared memory.

### 8.4 `failure_recovery_track`

Failure alone should not define identity. Recovery patterns matter.

Possible proposal forms:

- durable weakness candidate;
- reliable recovery candidate;
- unresolved rupture candidate.

Must preserve failure and recovery separately.

### 8.5 `preference_value_track`

Preference proposals should require repetition across time or explicit human confirmation.

Single preference-like episode should normally remain `lesson_candidate` or `shared_memory_candidate`.

### 8.6 `governance_risk_track`

Risk tracks should usually produce `governance_review_candidate`, not direct identity proposals.

Examples:

- self-authorizing memory attempt;
- receipt-only identity influence attempt;
- repeated contradiction cluster;
- cross-scope promotion attempt.

---

## 9. Proposal object requirements

An `IdentityProposalCandidate` should include:

- `proposal_id`
- `track_type`
- `aggregation_key`
- `continuity_level`
- `supporting_episode_refs`
- `counterevidence_episode_refs`
- `confidence_snapshot_ref`
- `proposed_identity_influence`
- `evidence_quality_summary`
- `governance_review_required`
- `rollback_plan_ref`
- `expires_or_revalidate_if`

Without these fields, the proposal should fail closed.

---

## 10. Revalidation and rollback

Identity influence should not be permanent by default.

Accepted proposals should carry:

- review timestamp;
- evidence basis;
- supersession rules;
- rollback conditions;
- revalidation triggers.

Examples of revalidation triggers:

- new material counterevidence;
- track confidence drop;
- repeated contradiction;
- human correction;
- policy change;
- scope expansion.

---

## 11. Examples

### Example A — local lesson only

One `expected_verified` episode for a publishing workflow.

Result:

```text
lesson_candidate = true
identity_proposal_candidate = false
```

Reason: one episode may teach locally but cannot change stable identity.

### Example B — competence proposal blocked

Three supporting episodes exist, but one recent `unexpected_verified` contradicting episode has strong independent observation.

Result:

```text
identity_proposal_candidate = false
counterevidence_review = required
```

Reason: counterevidence blocks high confidence.

### Example C — preference proposal candidate

Five separate human confirmations across time support the same delivery preference, with no contradiction.

Result:

```text
shared_memory_candidate = true
identity_proposal_candidate = possible
human review = recommended
```

Reason: durable preference update affects future interaction.

### Example D — governance risk

A track tries to promote receipt-only evidence into trust identity.

Result:

```text
governance_review_candidate = true
identity_proposal_candidate = false
```

Reason: verification sufficiency is not continuity authority.

---

## 12. Summary

Identity proposal thresholds prevent continuity inflation.

The key distinctions are:

- repeated experience is not automatically identity;
- support count is not enough without evidence quality;
- counterevidence is not passive;
- trust and governance tracks are stricter than local lessons;
- proposal is not update;
- governance remains separate from aggregation.

Core principle:

> Experience may influence continuity, but only governed continuity may reposition the identity center.
