# LS Architecture Map

## Status

Working architecture map for the LS repository.

This document is the shortest structural overview of LS as a system.
It explains the main layers, the core identity chain, the review/governance path,
and where key documents live.

It follows issue `#756`.

---

# 1. What LS is structurally

LS is not a single model and not just a prompt library.

It is a **continuity, evidence, governance, and review layer** that sits above model outputs and agent actions.

At a high level, LS tries to answer five different questions:

1. **What happened?**
2. **What repeated enough to matter?**
3. **What is allowed to change durable memory / identity / action state?**
4. **What is the active identity state right now?**
5. **How can a human inspect and challenge that state safely?**

---

# 2. The top-level LS stack

You can think of LS as five connected layers.

```text
Raw model / agent work
  -> Evidence and route layer
  -> Continuity and aggregation layer
  -> Identity governance layer
  -> Reconstructed identity layer
  -> Human review / dashboard layer
```

---

# 3. Layer-by-layer map

## Layer A — raw model / agent work

This is where an agent or model produces output, suggestions, plans, or actions.

Examples in LS:

- PR review trail runs
- route packets
- personal agent gateway outputs
- task-specific model completions

On its own, this layer is **not yet durable identity or governed memory**.

---

## Layer B — evidence and route layer

This layer captures how work was performed and what evidence supports it.

Representative LS areas:

- cooperative precision / PR review trail docs
- route stability probe artifacts
- reviewer evidence snapshots
- contributor route reports

This layer answers questions like:

- which route was used;
- which actor or role contributed;
- what evidence exists;
- whether the result can be replayed or checked.

Important property:

> evidence exists before durable identity claims are allowed.

---

## Layer C — continuity and aggregation layer

This layer turns isolated events into structured continuity records.

Core objects:

- `VerifiedEpisode`
- `TrackAggregationRecord`
- `ContinuityCoordinator`

This is the boundary between **one-off event** and **repeated pattern**.

Questions answered here:

- did this happen once or repeatedly?
- is it bounded to one workflow or broader?
- is the signal strong enough to become a proposal candidate?

Key LS issues already covering this zone:

- **#710** — continuity coordinator / aggregation / thresholds

---

## Layer D — identity governance layer

This layer decides whether a continuity pattern is allowed to affect durable identity state.

Core objects:

- `IdentityProposalCandidate`
- `GovernanceDecision`
- `IdentityUpdateRecord`
- `RollbackLedger`

This is the boundary between:

```text
interesting pattern
!=
approved identity change
```

Questions answered here:

- should this pattern become an identity proposal?
- was it approved, rejected, or quarantined?
- what durable identity update was actually written?
- how can that update later be rolled back or superseded?

Key LS issues already covering this zone:

- **#717** — identity proposal candidate / governance handoff
- **#721** — identity update record / rollback ledger

---

## Layer E — reconstructed identity layer

This layer answers the present-tense question:

> **Who is this agent right now, according to governed LS state?**

Core object:

- `IdentitySnapshot`

Supporting logic:

- snapshot reconstruction
- point-in-time filtering
- active vs inactive state resolution
- rollback / supersession / quarantine handling
- scope filtering

This layer is critical because LS does **not** treat all identity history as current identity.

Instead it reconstructs active state from governed records.

Key LS issue already covering this zone:

- **#727** — identity snapshot reconstruction

---

## Layer F — human review / dashboard layer

This is the visible control surface above reconstructed identity.

Core objects:

- `Identity Dashboard`
- `IdentityReviewAction`
- human review workflow

Questions answered here:

- what is currently active identity?
- what is pending / quarantined / rolled back?
- why does LS believe this?
- what can a human approve, reject, rollback, or annotate?

This layer is where LS becomes governable by inspection instead of only by hidden internal state.

Key LS issue already covering this zone:

- **#742** — identity dashboard / human review surface

---

# 4. The core identity chain

The most important LS architecture path currently looks like this:

```text
VerifiedEpisode
  -> TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdateRecord
  -> RollbackLedger
  -> IdentitySnapshot
  -> Identity Dashboard
  -> IdentityReviewAction
```

## Read it as a story

### `VerifiedEpisode`
A concrete verified event happened.

### `TrackAggregationRecord`
Multiple episodes were aggregated into a stronger continuity pattern.

### `IdentityProposalCandidate`
That pattern became a candidate for durable identity change.

### `GovernanceDecision`
LS governance approved, rejected, quarantined, or narrowed the candidate.

### `IdentityUpdateRecord`
An approved identity change became durable governed state.

### `RollbackLedger`
If later evidence contradicts or narrows that update, LS records rollback or supersession instead of silently rewriting history.

### `IdentitySnapshot`
LS reconstructs the active identity state at time `T`.

### `Identity Dashboard`
A human or reviewing agent sees the current identity state, pending items, and provenance.

### `IdentityReviewAction`
A reviewer submits an auditable action against governed identity state.

---

# 5. The fail-closed boundaries

LS is built around several fail-closed boundaries.

## Boundary 1 — evidence before durable claim
A useful output is not enough. Durable memory or identity claims need evidence.

## Boundary 2 — aggregation before proposal
One episode should not automatically become an identity update.

## Boundary 3 — governance before durable identity mutation
A proposal is not an approved identity change.

## Boundary 4 — rollback instead of silent rewrite
Historical identity changes should not disappear without trace.

## Boundary 5 — reconstructed active state instead of “all history = current identity”
Current identity must be rebuilt from governed state.

## Boundary 6 — human review action is not direct mutation
A dashboard click or review action should route through governed logic, not bypass it.

---

# 6. State classes LS tries to keep separate

One of the most important architectural rules in LS is **state separation**.

At minimum, LS distinguishes:

## 6.1 Raw / observed material
Episodes, route traces, and evidence that may matter later.

## 6.2 Aggregated continuity material
Patterns strong enough to discuss, but not yet approved as identity.

## 6.3 Proposed identity state
Candidates under governance review.

## 6.4 Durable governed identity state
Approved updates that have actually entered the identity ledger.

## 6.5 Historical inactive identity state
Rolled-back, superseded, expired, or quarantined updates.

## 6.6 Reconstructed active identity state
The point-in-time active identity center exposed by `IdentitySnapshot`.

## 6.7 Human review state
Annotations, rollback requests, review actions, and revalidation events.

If these states collapse into one another, LS becomes unsafe and hard to reason about.

---

# 7. Where to read what

## Identity continuity path

- `docs/identity-snapshot.md`
- `docs/snapshot-reconstruction.md`
- `docs/identity-dashboard.md`
- `docs/human-review-workflow.md`
- `schemas/identity_snapshot.example.json`
- `schemas/identity_review_action.example.json`

## Governance / update / rollback path

- `docs/governance-handoff.md`
- `docs/identity-update-record.md`
- `docs/rollback-ledger.md`

## Cooperative precision / evidence / route work

- `docs/COGNITIVE_TRAIL_NETWORK.md`
- `docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md`
- `docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md`
- `docs/COOPERATIVE_PRECISION_STACK.md`
- `docs/COOPERATIVE_PRECISION_METRICS.md`

## Personal AI operating layer / PCG direction

- `docs/LS_PERSONAL_COGNITIVE_GARDEN.md`
- `docs/PERSONAL_GROWTH_ENTRY.md`
- `docs/personal-agent-gateway-runtime.md`
- `docs/positioning/personal-ai-operating-layer.md`

---

# 8. Completed architecture spine so far

These issues already form the first explicit LS identity spine:

- **#710** — continuity coordinator / aggregation / thresholds
- **#717** — identity proposal candidate / governance handoff
- **#721** — identity update record / rollback ledger
- **#727** — identity snapshot reconstruction
- **#742** — identity dashboard / human review surface
- **#756** — architecture map / README / roadmap layer

---

# 9. What this architecture now allows LS to say

LS can now describe a governed continuity story like this:

```text
A verified pattern happened repeatedly.
It crossed a threshold.
It became an identity proposal.
Governance approved a bounded durable update.
Later evidence narrowed or challenged it.
Rollback history preserved that correction.
A current snapshot reconstructed what remains active.
A human reviewer can inspect the result and act on it without bypassing governance.
```

That is the core architectural promise of LS today.

---

# 10. Summary

If you only remember one thing from this map, let it be this:

```text
LS is not just memory.
LS is a governed path from evidence and repeated experience
into durable identity state and human-reviewable continuity.
```

Or even shorter:

```text
episode -> pattern -> proposal -> governance -> durable update -> rollbackable history -> current identity -> human review
```
