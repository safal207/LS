# Continuity Vocabulary

## Status

Design note for LS continuity architecture.

This document defines a small shared vocabulary for the OVC → VerifiedEpisode → continuity path.

It follows:

- `docs/bronnikov-to-ls.md`
- `docs/verified-episode-prism.md`
- `docs/evidence-channels.md`
- `schemas/verified_episode.example.json`
- issue `#704`

The purpose is to make continuity terms explicit enough that retained experience does not silently acquire identity influence just by existing.

---

# 1. Core boundary

The central LS boundary is:

```text
VerifiedEpisode != stable identity update
```

and:

```text
retained experience != self-authorizing memory
```

A verified episode may influence continuity only through explicit vocabulary, aggregation, and governance gates.

---

# 2. `continuity_level`

`continuity_level` describes the scope at which an episode may be considered.

It does **not** mean the episode has already changed identity.

## Values

### `individual`

The episode may matter only to one agent's local learning or history.

Examples:

- local skill improvement
- local failure memory
- local preference adaptation

### `relational`

The episode may matter to a relationship or shared context.

Examples:

- delegation continuity
- handoff quality
- trust repair or trust break
- human-agent cooperation pattern

### `system`

The episode may matter to system-level governance, policy, or durable norms.

Examples:

- repeated safety failure pattern
- policy-impacting verified behavior
- cross-agent shared-memory failure mode
- governance-review candidate

## Default rule

If `continuity_level` is absent, LS should treat it as:

```text
individual + history_only
```

not as system-wide influence.

---

# 3. `eligible_influence`

`eligible_influence` describes what the episode is allowed to affect next.

It is a gate, not an outcome.

## Values

### `history_only`

The episode may remain queryable but should not affect learning, shared memory, or identity.

Used for:

- audit-only retention
- superseded records
- weak evidence
- unresolved contradictions

### `lesson_candidate`

The episode may be considered by a learning layer.

Used for:

- expected verified outcomes
- failed verified outcomes
- unexpected verified outcomes
- local strategy improvement

Important boundary:

```text
lesson_candidate != identity_update
```

### `shared_memory_candidate`

The episode may be proposed for shared or group memory.

Used for:

- team-relevant observations
- handoff outcomes
- cross-agent coordination memory

Important boundary:

Shared-memory promotion should require provenance and scope checks. Repeated recall should not silently promote authority.

### `identity_proposal_candidate`

The episode may be included in an aggregation process that proposes identity influence.

Used for:

- repeated verified competence patterns
- repeated verified failure patterns
- durable preference or relationship shifts

Important boundary:

A single episode should not directly become stable identity evidence.

### `governance_review_candidate`

The episode may require policy, safety, or continuity governance review.

Used for:

- high-risk action outcomes
- policy-impacting contradiction
- self-authored evidence concerns
- cross-scope memory poisoning / laundering risk

---

# 4. `episode_outcome_class`

`episode_outcome_class` describes what kind of outcome was verified or not verified.

It must remain separate from success and identity influence.

## Values

### `expected_verified`

The expected transition was verified.

May support:

- `supporting` evidence role
- `lesson_candidate`

Must not automatically imply:

- identity update
- system-level competence claim

### `failed_verified`

A failure was verified.

May support:

- `failure` evidence role
- counter-learning
- reliability / recovery analysis

Must not be collapsed into success just because the observation was verified.

### `unexpected_verified`

An unexpected outcome was verified.

May support:

- `contradicting` evidence role
- model correction
- investigation

Must remain distinct from expected success.

### `unverified`

Outcome was not sufficiently verified.

Default handling:

- reject experience eligibility or keep as history-only / investigation context

### `contradicted`

Evidence channels conflict in a way that prevents a trusted verified result.

Default handling:

- fail closed
- investigate
- do not count as supporting evidence

---

# 5. `evidence_role`

`evidence_role` describes how a retained episode contributes to later aggregation.

It does not itself decide identity.

## Values

### `supporting`

Evidence supports the expected transition or lesson.

Allowed only when expected outcome is actually verified and not superseded.

### `failure`

Evidence shows a verified failure.

Used for failure learning, recovery, and reliability analysis.

### `contradicting`

Evidence contradicts the expected transition or prior belief.

Used for model correction and investigation.

### `counterevidence`

Evidence weakens an existing continuity pattern or identity proposal.

Useful when aggregation has prior supporting evidence but later verified outcomes challenge it.

### `historical_only`

Retained for audit or context, but not counted in active aggregation.

Used for:

- superseded episodes
- redacted episodes
- weak or partial evidence
- non-current support

---

# 6. `retention_status`

`retention_status` describes whether and how the episode remains retained.

## Values

### `active`

Episode is currently retained and may participate according to its `eligible_influence`.

### `superseded`

Episode remains queryable but should not count as current supporting evidence.

### `retained_for_audit`

Episode is retained for audit, replay protection, or provenance history only.

### `redacted`

Episode payload is partially removed or hidden, while required provenance / digest may remain.

### `expired`

Episode should no longer be used for active influence.

May remain as digest-only or audit-only depending on policy.

---

# 7. `identity_update_eligible`

`identity_update_eligible` is a boolean gate.

Default value should be:

```json
false
```

It may only become true after appropriate aggregation and governance logic.

## Forbidden interpretation

```text
identity_update_eligible=true
```

must not mean:

- identity has already changed,
- the episode alone is sufficient,
- the evidence self-authorizes identity influence.

It only means the episode or aggregated pattern may enter an identity proposal process.

---

# 8. Default fail-closed behavior

When vocabulary is missing or ambiguous, LS should prefer fail-closed outcomes.

## Examples

| Missing / ambiguous field | Default behavior |
|---|---|
| missing `continuity_level` | treat as `individual` + `history_only` |
| missing `eligible_influence` | no continuity influence |
| missing `expected_transition_ref` | reject experience eligibility |
| missing `observer_independence_basis` | reject or investigate |
| `actor_assertion` only | context only, not trusted experience |
| `runtime_receipt` only | execution evidence only, not identity influence |
| superseded episode | queryable, but not current support |
| single episode requests identity mutation | reject |

---

# 9. Relationship to VerifiedEpisode Prism

The vocabulary maps directly to prism layers:

| Vocabulary | Prism layer |
|---|---|
| `episode_outcome_class` | Verified Outcome |
| `evidence_role` | Retained Experience |
| `retention_status` | Retained Experience |
| `continuity_level` | Identity Eligibility |
| `eligible_influence` | Identity Eligibility |
| `identity_update_eligible` | Identity Eligibility |

---

# 10. Relationship to Evidence Channels

Evidence channels help decide whether an episode is eligible for a given vocabulary state.

For example:

- `actor_assertion` alone should not create `supporting` trusted experience.
- `runtime_receipt` may support execution verification but not identity influence.
- `target_observation` may support expected-transition verification.
- `independent_observer` plus `observer_independence_basis` may strengthen trusted experience eligibility.
- `human_confirmation` may be decisive for human-valued outcomes, but should remain typed separately.

---

# 11. Summary

This vocabulary exists to prevent continuity inflation.

The important distinctions are:

- verified outcome is not automatically success;
- retained experience is not automatically identity evidence;
- evidence role is not identity role;
- continuity level is not authority;
- eligible influence is a gate, not a completed update.

The core rule remains:

> Experience may influence continuity, but only governed continuity may reposition the identity center.
