# Evidence Channels

## Status

Design note for LS continuity architecture.

This document defines **evidence channels** for OVC and VerifiedEpisode so that LS can reason about verification inputs as typed signals rather than a flat list of evidence blobs.

It follows:

- `docs/bronnikov-to-ls.md`
- `docs/verified-episode-prism.md`
- issue `#704`

The main goal is to preserve a strict boundary between:

- **what can help verify an outcome**, and
- **what is allowed to influence continuity / identity**.

---

# 1. Why evidence channels exist

If LS stores verification evidence as an untyped list, several dangerous collapses become likely:

- actor assertion can be confused with independent observation;
- runtime receipt can be treated as equivalent to target-state confirmation;
- relayed human confirmation can be treated as if it were direct system evidence;
- repeated evidence reuse can look like stronger truth even when it comes from the same source class;
- retained verification material can silently turn into continuity authority.

Evidence channels exist to prevent those collapses.

An evidence channel answers not only **what evidence exists**, but also:

- what *kind* of evidence it is,
- how close it is to the action or target,
- whether it is independent of actor / tool / receipt issuer,
- and whether it may support only verification, or also continuity influence under additional constraints.

---

# 2. Core principle

Evidence channels are typed verification inputs, not interchangeable trust tokens.

A channel may be sufficient to:

- confirm that an action ran,
- confirm that a receipt exists,
- confirm that a target changed,
- confirm that a human observed something,
- confirm that a delegated counterparty acknowledged the result.

That does **not** mean the same channel may:

- support identity influence,
- support stable competence claims,
- support trust repair,
- or override contradictory channels.

Verification sufficiency and continuity influence must remain separate decisions.

---

# 3. Candidate evidence channel taxonomy

LS should treat at least the following channel kinds as distinct.

## 3.1 `actor_assertion`

What the actor claims happened.

Examples:

- "I completed the action"
- agent-generated self-report
- post-hoc explanation emitted by the actor

### Typical strengths

- useful as context
- useful for debugging intent vs result mismatch
- useful when compared against verified outcome

### Typical limitations

- not independent
- cannot on its own prove successful outcome
- cannot on its own support identity influence

### Default continuity rule

`actor_assertion` may support investigation and episode context, but must not be sufficient for trusted experience on its own.

---

## 3.2 `runtime_receipt`

What the runtime / tool / execution environment says happened.

Examples:

- command completed with exit status
- API call receipt
- transaction ID
- workflow execution trace

### Typical strengths

- proves an execution attempt occurred
- often good for exact timing and parameters
- may prove that a system accepted a request

### Typical limitations

- may not prove target-state change
- may be issued by the same system that executed the action
- may still be dependent on actor-controlled infrastructure

### Default continuity rule

`runtime_receipt` is strong execution evidence, but it should not automatically count as target verification or identity evidence.

---

## 3.3 `target_observation`

What the affected target or environment shows after the action.

Examples:

- document state changed
- database row exists or was updated
- external system status changed
- observable side effect appears on target

### Typical strengths

- often the strongest evidence that the intended transition actually happened
- directly connected to expected target-state verification
- can distinguish successful execution from mere receipt issuance

### Typical limitations

- may still require interpretation
- may not reveal *who* caused the change
- may be delayed or partially observable

### Default continuity rule

`target_observation` is a high-value channel for expected-transition verification, but may still require actor/receipt linkage and independence checks before continuity influence.

---

## 3.4 `independent_observer`

What an observer independent of actor, tool, and receipt issuer confirms.

Examples:

- separate monitoring service
- separate operator review
- independent human verifier
- separate telemetry stream with its own control path

### Typical strengths

- critical for fail-closed verification
- helps break self-authored evidence loops
- can validate or contradict actor/runtime claims

### Typical limitations

- independence must be justified, not assumed
- an observer may still be mistaken or incomplete
- different observers may conflict

### Required companion field

When this channel is used, LS should preserve:

- `observer_independence_basis`

This should explain **why** the observer is independent of:

- the actor,
- the tool/runtime,
- the receipt issuer,
- and, where relevant, the delegated counterparty.

### Default continuity rule

`independent_observer` is one of the strongest channels for trusted retained experience, but it is not a blanket authority source. It still must remain provenance-bound.

---

## 3.5 `relational_counterparty`

What the delegated peer, handoff receiver, consent counterparty, or other relational participant confirms.

Examples:

- a delegated agent acknowledges receiving or completing a handoff
- a human confirms that a requested action was delivered to them
- a collaborating agent confirms shared task completion

### Typical strengths

- essential for relational continuity
- useful for delegation, handoff, and consent verification
- captures evidence unavailable in pure target telemetry

### Typical limitations

- may not be independent
- may be socially coupled to the actor
- may prove acknowledgement but not actual target-state success

### Default continuity rule

`relational_counterparty` is important for relational continuity, but should not automatically substitute for target verification or independent observation.

---

## 3.6 `human_confirmation`

What a human explicitly confirms or denies.

Examples:

- “yes, the draft was useful”
- “no, the file was not uploaded correctly”
- “I received the handoff and it matches expectations”

### Typical strengths

- crucial for human-facing tasks
- captures subjective success and relational acceptance
- may be the only source for some classes of outcome

### Typical limitations

- may be subjective rather than target-state exact
- may not prove the underlying mechanism
- may be delayed, partial, or inconsistent

### Default continuity rule

`human_confirmation` may be decisive for human-value outcomes, but should still be distinguished from infrastructure-level verification and from independent system observation.

---

# 4. Channel properties LS should preserve

Every evidence channel entry should carry enough metadata to reason about its role.

## Candidate per-channel fields

- `kind`
- `evidence_digest`
- `source_ref`
- `observed_at`
- `independent`
- `observer_independence_basis`
- `supports_verification`
- `supports_continuity_influence`
- `confidence_scope`
- `notes`

## Example shape

```json
{
  "kind": "independent_observer",
  "evidence_digest": "sha256:...",
  "source_ref": "observer:telemetry:7",
  "observed_at": "2026-06-25T04:00:00Z",
  "independent": true,
  "observer_independence_basis": "separate monitoring plane with no write path to actor runtime",
  "supports_verification": true,
  "supports_continuity_influence": true,
  "confidence_scope": "expected_transition_verification"
}
```

---

# 5. Verification sufficiency vs continuity influence

One of the main jobs of channel typing is to prevent a silent jump from **verification** to **identity influence**.

## 5.1 Verification sufficiency question

For a given action class, do we have enough evidence to say:

- the action executed,
- the expected transition occurred,
- the outcome is verified / contradicted / unresolved?

## 5.2 Continuity influence question

Even if the outcome is verified, do we have the right evidence shape to let the episode influence:

- lesson formation,
- relational trust,
- competence track,
- identity proposal,
- governance review?

These are separate gates.

---

# 6. Default channel constraints by continuity safety

The exact rules may vary by action class, but LS should start with conservative defaults.

## 6.1 Channels that should never be sufficient on their own for trusted experience

By default, the following should **not** be enough alone to create trusted continuity evidence:

- `actor_assertion`
- `runtime_receipt`
- `relational_counterparty` (unless the action class is specifically relational and independently bounded)

## 6.2 Channels that may strongly support expected-transition verification

Usually stronger:

- `target_observation`
- `independent_observer`
- `human_confirmation` (for human-valued outcomes)

But even these should not bypass provenance or aggregation boundaries.

## 6.3 Identity influence should usually require more than one channel family

As a default fail-closed posture, identity-relevant experience should typically require at least a combination such as:

- execution evidence (`runtime_receipt` or equivalent)
- transition evidence (`target_observation` and/or strong `human_confirmation` depending on task)
- and an independence-bearing channel (`independent_observer`, or an explicitly justified equivalent)

This is a design direction, not yet a final hard rule.

---

# 7. Action-class-specific channel requirements

Channel sufficiency should depend on action class.

## Example classes

### A. Pure infrastructure action
Examples:
- publish artifact
- run migration
- upload file

Likely needs:
- `runtime_receipt`
- `target_observation`
- maybe `independent_observer` for durable continuity impact

### B. Human-facing delivery action
Examples:
- send draft
- hand over result to user
- produce explanation or recommendation

Likely needs:
- `runtime_receipt` or delivery receipt
- `human_confirmation` and/or `relational_counterparty`
- optional `independent_observer` depending on risk

### C. Delegation / handoff action
Examples:
- assign work to another agent
- transfer task ownership
- hand off approval context

Likely needs:
- `runtime_receipt`
- `relational_counterparty`
- and in some cases target or observer evidence if the handoff is expected to produce a system effect

### D. High-risk continuity or identity-relevant action
Examples:
- actions later used as competence evidence
- actions affecting trust / governance / policy tracks

Likely needs:
- explicit expected transition provenance
- strong target confirmation
- independence-bearing observer evidence
- stricter contradiction handling

---

# 8. Contradiction and dependency handling

Evidence channels should not be treated as additive truth points.

LS should be able to represent:

- **agreement** — channels support the same outcome
- **contradiction** — channels point to incompatible outcomes
- **dependency** — two channels derive from the same underlying source
- **insufficient coverage** — channels exist but do not answer the expected-transition question

## Examples

### Contradiction
- `runtime_receipt` says success
- `target_observation` shows no state change

### Dependency
- a human report is copied directly from the actor’s own self-report
- a monitoring stream is emitted by the same runtime process that issued the receipt

### Insufficient coverage
- receipt exists, but no channel observes the target state

---

# 9. Relationship to VerifiedEpisode Prism

Evidence channels primarily feed **Layer 4 — Verified Outcome** in `docs/verified-episode-prism.md`.

They may also affect:

- Layer 5 — Retained Experience, because evidence role and retention status depend on what was actually verified;
- Layer 6 — Identity Eligibility, because continuity influence should depend in part on channel quality and independence.

But channels alone do not define:

- orientation source,
- intended transition,
- or governance-level continuity eligibility.

---

# 10. Relationship to OVC

OVC should not only aggregate evidence digests. It should also preserve channel semantics.

At minimum, OVC should be able to answer:

- which channel kinds were present?
- which were missing for this action class?
- which channels were independent?
- what was the `observer_independence_basis`?
- which contradictions remained unresolved?
- which channels supported only execution, and which supported expected-transition verification?

---

# 11. Non-goals

This document does not yet define:

- exact scoring / weighting between channels,
- final contradiction resolution policy,
- storage schema for all channel metadata,
- retrieval ranking rules.

Its purpose is to establish **typed channel semantics and continuity constraints**.

---

# 12. Summary

Evidence channels let LS treat verification inputs as structured signal classes rather than one flat evidence bag.

The core channel kinds are:

1. `actor_assertion`
2. `runtime_receipt`
3. `target_observation`
4. `independent_observer`
5. `relational_counterparty`
6. `human_confirmation`

The key architectural boundary is:

> evidence that helps verify an outcome is not automatically evidence that may influence continuity or identity.

Channel typing exists to preserve that boundary and keep OVC / VerifiedEpisode / continuity behavior fail-closed rather than self-authorizing.
