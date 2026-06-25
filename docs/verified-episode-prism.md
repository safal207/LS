# VerifiedEpisode Prism

## Status

Design note for LS continuity architecture.

This document defines **VerifiedEpisode** as a multi-layer continuity object rather than a flat retained memory item. It is intended as a follow-up to:

- `docs/bronnikov-to-ls.md`
- OVC / VerifiedEpisode provenance work
- issue `#704` (continuity follow-up artifacts)

The purpose of the prism model is to make one boundary explicit:

> a verified episode may become durable experience input, but it must not become self-authorizing identity evidence just because it is retained.

---

# 1. Why a prism model exists

A single action episode in LS carries multiple distinct roles at once:

- it comes from some orientation state,
- it encodes an expected transition,
- it produces an executed action,
- it yields one or more observed outcomes,
- it may be retained as experience,
- and it may or may not become eligible to influence continuity / identity.

If these layers are flattened into one memory record, LS loses critical boundaries:

- expected vs observed outcome,
- actor claim vs verified outcome,
- retained experience vs identity evidence,
- local lesson vs continuity-wide influence.

The prism model exists to preserve those distinctions explicitly.

---

# 2. Core principle

VerifiedEpisode is **not** a synonym for identity evidence.

A VerifiedEpisode may:

- preserve the verified influence of an action and its outcome,
- support learning,
- remain queryable as history,
- become a candidate input to continuity aggregation.

A VerifiedEpisode may **not** by itself:

- rewrite stable identity,
- elevate its own authority,
- become durable norm evidence by retention alone,
- collapse provenance boundaries between actor, verifier, observer, and continuity review.

---

# 3. Prism layers

VerifiedEpisode is modeled as a six-layer object.

## Layer 1 — Orientation Source

Describes where the action candidate came from.

Possible inputs:

- TOC result
- RTOC result
- PATOC result
- prior memory / retrieved context
- delegation / handoff context
- consent / authority context

Questions this layer answers:

- what orientation state preceded the action?
- what prior continuity state or memory influenced it?
- was the action self-initiated, delegated, or inherited from a handoff?

### Candidate fields

- `toc_result_ref`
- `rtoc_result_ref`
- `patoc_result_ref`
- `memory_input_refs[]`
- `delegation_ref`
- `handoff_ref`
- `consent_context_ref`

---

## Layer 2 — Intended Transition

Describes what the agent expected to happen if the action succeeded.

This layer exists to prevent LS from reconstructing expected outcome from action digest alone.

### Candidate fields

- `expected_transition_ref`
- `patoc_result_ref`
- `expected_outcome_digest`
- `expected_target_state_ref`
- `transition_scope`

Questions this layer answers:

- what transition was the action trying to produce?
- where did that expectation come from?
- what target state or side effect was expected?

---

## Layer 3 — Executed Action

Describes what was actually executed.

### Candidate fields

- `action_digest`
- `actor_ref`
- `target_ref`
- `tool_ref`
- `parameters_digest`
- `receipt_ref`
- `executed_at`

Questions this layer answers:

- what action actually ran?
- who or what executed it?
- against which target?
- under which receipt or runtime trace?

---

## Layer 4 — Verified Outcome

Describes what outcome verification established.

This layer is where actor assertion must be separated from independently verified result.

### Candidate fields

- `ovc_result_ref`
- `verification_result_digest`
- `observer_set_digest`
- `observer_independence_basis`
- `episode_outcome_class`
- `expected_state_matched`
- `verification_timestamp`

### Outcome classes

At minimum, LS should distinguish:

- `expected_verified`
- `unexpected_verified`
- `failed_verified`
- `unverified`
- `contradicted`

Questions this layer answers:

- what was actually verified?
- who observed it?
- why were observers considered independent?
- did observed outcome match the expected transition?

---

## Layer 5 — Retained Experience

Describes how the episode is retained in continuity memory.

This layer is about **experience retention**, not identity mutation.

### Candidate fields

- `evidence_role`
- `retention_status`
- `superseded_by`
- `redaction_status`
- `replay_status`
- `query_visibility`
- `retained_at`

### Candidate evidence roles

- `supporting`
- `failure`
- `contradicting`
- `counterevidence`
- `historical_only`

### Candidate retention states

- `active`
- `superseded`
- `retained_for_audit`
- `redacted`
- `expired`

Questions this layer answers:

- is this episode still active supporting evidence?
- has it been superseded?
- is it retained only for audit / replay / history?
- what role does it play in later learning?

---

## Layer 6 — Identity Eligibility

Describes whether the retained episode may influence continuity aggregation or identity proposals.

This layer exists to make the final LS boundary explicit:

```text
VerifiedEpisode != stable identity update
```

### Candidate fields

- `continuity_level`
- `eligible_influence`
- `identity_update_eligible`
- `aggregation_gate_ref`
- `governance_review_required`

### Candidate continuity levels

- `individual`
- `relational`
- `system`

### Candidate eligible influence values

- `history_only`
- `lesson_candidate`
- `shared_memory_candidate`
- `identity_proposal_candidate`
- `governance_review_candidate`

Questions this layer answers:

- may this episode influence only local learning, or continuity more broadly?
- does it require governance review before identity impact?
- is it completely ineligible for identity influence despite being retained?

---

# 4. Cross-layer invariants

The prism model is useful only if the layers are prevented from collapsing into each other.

## Invariant 1 — expected transition is explicit

Expected outcome must not be reconstructed from action digest coincidence alone.

LS should preserve explicit provenance via:

- `expected_transition_ref`
- `patoc_result_ref`
- target-state expectation references where relevant

## Invariant 2 — verified outcome is not actor assertion

Actor claim, runtime receipt, target observation, and independent observer confirmation must remain distinguishable.

## Invariant 3 — retained experience is not identity evidence

Retention does not automatically imply identity eligibility.

An episode may be retained while still being:

- history-only,
- lesson-only,
- audit-only,
- or blocked from identity influence.

## Invariant 4 — superseded episodes remain queryable but lose current support role

A superseded episode may still be visible for audit or historical continuity, but it must not continue to count as current supporting evidence.

## Invariant 5 — one episode cannot self-authorize continuity influence

No single VerifiedEpisode should be able to elevate itself into stable identity evidence without passing through explicit aggregation / governance gates.

---

# 5. Prism view as control flow

```text
Orientation source
    ↓
Intended transition
    ↓
Executed action
    ↓
Verified outcome
    ↓
Retained experience
    ↓
Identity eligibility
```

This does **not** mean the layers are strictly temporal serialization only.

It means a valid VerifiedEpisode should preserve these six distinct views of the same continuity event.

---

# 6. Example shape

```json
{
  "orientation_source": {
    "patoc_result_ref": "patoc:abc123",
    "memory_input_refs": ["mem:1", "mem:2"]
  },
  "intended_transition": {
    "expected_transition_ref": "triad:expected:7",
    "expected_target_state_ref": "state:after_publish"
  },
  "executed_action": {
    "action_digest": "sha256:...",
    "actor_ref": "agent:writer",
    "target_ref": "doc:post-42",
    "receipt_ref": "receipt:run-991"
  },
  "verified_outcome": {
    "ovc_result_ref": "ovc:result:991",
    "episode_outcome_class": "expected_verified",
    "observer_set_digest": "sha256:obs...",
    "observer_independence_basis": "runtime receipt + independent human review"
  },
  "retained_experience": {
    "evidence_role": "supporting",
    "retention_status": "active"
  },
  "identity_eligibility": {
    "continuity_level": "individual",
    "eligible_influence": "lesson_candidate",
    "identity_update_eligible": false
  }
}
```

---

# 7. Relationship to OVC

OVC does not own the entire prism.

OVC primarily establishes **Layer 4 — Verified Outcome** and contributes evidence to Layer 5.

But OVC output alone is not enough to define:

- orientation source,
- intended transition provenance,
- continuity level,
- identity eligibility.

Those belong to the broader continuity architecture around OVC.

---

# 8. Relationship to ContinuityCoordinator

ContinuityCoordinator should operate **above** the VerifiedEpisode retention layer.

Its role is not to verify the episode itself, but to decide:

- how episodes aggregate across tracks,
- whether repeated patterns matter,
- whether continuity influence should remain local,
- and whether any identity proposal should proceed to governed review.

In other words:

- OVC verifies outcome,
- VerifiedEpisode preserves continuity-structured experience,
- ContinuityCoordinator decides whether multiple retained experiences have any right to influence identity.

---

# 9. Non-goals

This document does not define:

- the full OVC evidence channel taxonomy,
- exact persistence / storage format,
- ranking or retrieval heuristics,
- the final governance decision model.

Those should be specified in follow-up continuity documents.

---

# 10. Summary

VerifiedEpisode should be modeled as a prism with six layers:

1. orientation source
2. intended transition
3. executed action
4. verified outcome
5. retained experience
6. identity eligibility

This structure helps LS preserve the boundaries that matter most:

- expected vs observed,
- actor claim vs verified result,
- retained experience vs identity evidence,
- local learning vs governed continuity influence.

The core rule remains:

> a verified episode may become durable experience input, but it must not become self-authorizing identity evidence just because it is retained.
