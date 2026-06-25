# LS Roadmap

## Status

Working roadmap for LS after the first continuity / identity / review architecture spine.

This roadmap follows issue `#756` and should be read with:

- `README.md`
- `docs/architecture-map.md`

---

# 1. Current architecture baseline

LS now has a first full identity-continuity path:

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

This is the current architecture spine.

The next work should make this spine easier to validate, demonstrate, and contribute to.

---

# 2. Completed blocks

## 2.1 Continuity and aggregation

Completed:

- continuity coordinator direction;
- track aggregation framing;
- threshold boundary between repeated evidence and identity proposal.

Primary issue:

- **#710** — ContinuityCoordinator / aggregation / thresholds

---

## 2.2 Identity proposal and governance handoff

Completed:

- `IdentityProposalCandidate` boundary;
- proposal vs identity update separation;
- governance handoff framing;
- fail-closed proposal guards.

Primary issue:

- **#717** — IdentityProposalCandidate / governance handoff

---

## 2.3 Identity update and rollback ledger

Completed:

- `IdentityUpdateRecord` concept;
- rollback ledger semantics;
- supersession and rollback distinction;
- active-state lifecycle framing.

Primary issue:

- **#721** — IdentityUpdateRecord / RollbackLedger

---

## 2.4 Identity snapshot reconstruction

Completed:

- `IdentitySnapshot` concept;
- active identity reconstruction from governed state;
- point-in-time reconstruction rules;
- rollback / supersession / quarantine filtering.

Primary issue:

- **#727** — IdentitySnapshot reconstruction

---

## 2.5 Human review surface

Completed:

- Identity Dashboard surface;
- human review workflow;
- `IdentityReviewAction` example;
- stale-view protection and exact material binding.

Primary issue:

- **#742** — Identity Dashboard / human review surface

---

## 2.6 Repository entrance and architecture map

In progress / current block:

- README architecture entry;
- architecture map;
- roadmap.

Primary issue:

- **#756** — Architecture map and README overhaul

---

# 3. Near-term priorities

## Priority 1 — schema hardening

Move selected reference examples toward stricter schemas and validators.

Candidate tasks:

- promote key examples into normative JSON Schema files;
- add validation tests for examples;
- check naming consistency across references;
- define required vs optional fields;
- add negative fixtures for fail-closed cases.

Good first targets:

- `schemas/identity_snapshot.example.json`
- `schemas/identity_review_action.example.json`
- `schemas/identity_update_record.example.json`

---

## Priority 2 — demo scenario

Create one readable end-to-end demo showing the full LS identity path.

Candidate demo:

```text
VerifiedEpisode samples
  -> TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdateRecord
  -> RollbackLedger
  -> IdentitySnapshot
  -> IdentityReviewAction
```

Suggested artifact:

- `docs/demo-identity-cycle.md`
- `examples/identity-cycle/full_identity_cycle.example.json`

Goal:

> make the architecture visible as one small story instead of many separate documents.

---

## Priority 3 — architecture consistency pass

Make the repo easier to navigate.

Candidate tasks:

- add cross-links between identity docs;
- normalize names and casing;
- align example IDs across docs and schemas;
- make issue numbers visible in relevant docs;
- identify outdated or duplicated explanations.

---

## Priority 4 — contributor-friendly tasks

Create small tasks that external contributors can complete without understanding the full system.

Examples:

- validate one schema example;
- add one negative fixture;
- add one glossary entry;
- improve one diagram;
- test one demo command;
- check one document for broken links.

---

# 4. Medium-term product directions

## 4.1 Identity dashboard prototype

Turn the dashboard design into a minimal mock / static prototype.

Possible artifacts:

- static HTML mock;
- screenshot-oriented product spec;
- JSON-to-dashboard renderer;
- simple read-only view over example snapshot data.

---

## 4.2 Human review API sketch

Define the API boundary more formally.

Candidate endpoints:

```text
GET  /api/identity/snapshot
GET  /api/identity/snapshot/{snapshot_id}
GET  /api/identity/snapshot/compare?from=...&to=...
POST /api/identity/review-actions
GET  /api/identity/review-actions/{action_id}
```

Important invariant:

> review actions create auditable requests; they do not directly mutate identity.

---

## 4.3 Governance decision validators

Add validation logic for governance-bound identity updates.

Focus areas:

- proposal cannot approve itself;
- update requires governance decision;
- rollback requires update/application binding;
- stale snapshot review action returns revalidation;
- missing provenance fails closed.

---

## 4.4 Multi-agent / relational snapshots

Extend snapshot examples to show:

- individual agent identity;
- relationship-specific overlay;
- shared memory boundary;
- system-level constraints.

Goal:

> keep relational memory useful without silently promoting it into global identity.

---

# 5. Longer-term directions

## 5.1 LS as an identity-aware agent OS layer

Use LS as a layer above multiple tools and agents, preserving:

- continuity;
- evidence;
- governance;
- rollback;
- human review.

## 5.2 External validation

Invite reviewers to challenge:

- schema shape;
- fail-closed boundaries;
- auditability;
- privacy and scope assumptions;
- usefulness of dashboard flows.

## 5.3 Integration with cooperative precision work

Connect identity architecture to existing LS work around:

- PR review trails;
- route stability;
- role contribution metrics;
- cognitive trail validation;
- personal cognitive garden workflows.

---

# 6. Suggested next issues

## `Schema hardening for identity examples`

Turn reference examples into more formal schemas and test fixtures.

## `End-to-end identity cycle demo`

Create one complete demo story that shows the whole chain.

## `Identity dashboard prototype`

Build a simple read-only dashboard view from `identity_snapshot.example.json`.

## `Contributor good-first map`

Create a short list of low-risk tasks for new contributors.

---

# 7. Roadmap principle

The next phase should prefer:

```text
explainable demo + schema validation + contributor entry
```

over adding too many new abstract layers.

Core principle:

> LS should now become easier to verify, easier to demo, and easier to join.
