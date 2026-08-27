# Route governance compatibility

## Status

Draft architecture decision and manual compatibility specimen for issue #773.

This document answers a narrow question:

> Should route promotion reuse the existing LS identity-governance spine, or
> should Route Artifact v2 create a separate generic governance lifecycle?

## 1. Repository finding

LS already documents this identity-governance topology:

```text
VerifiedEpisode
  -> TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdateRecord
  -> RollbackLedger
  -> IdentitySnapshot
```

Route promotion has the same high-level topology:

```text
TrailRun / EvidenceBundle
  -> RoutePromotionCandidate
  -> GovernanceDecision
  -> RouteVersionRecord
  -> RouteLedgerEntry
  -> RouteRegistrySnapshot
```

The topology is shared. The domain semantics are not.

The existing identity documents are design notes, and several checked-in JSON
files are explicitly reference examples rather than normative generic schemas.
Therefore this repository currently proves a mature governance pattern, not yet
a universal runtime substrate that Route Artifact can adopt without an adapter.

## 2. Provisional decision

Use **Option B: shared governance envelope with domain-specific records**.

Do not make `RoutePromotionCandidate` an `IdentityProposalCandidate`.
Do not encode route evidence as identity metadata.
Do not create a second unrelated governance vocabulary either.

Reuse the following governance invariants:

- candidate and durable update remain separate;
- proposing actor cannot approve its own candidate;
- governance decision binds to the exact candidate digest and evidence set;
- support and counterevidence remain distinguishable;
- later material changes invalidate the prior decision binding;
- supersession and rollback create new records instead of rewriting history;
- current active state is reconstructed from governed records and ledger events;
- memory and evidence grant no action authority.

Keep the following route-specific:

- Git repository and exact HEAD binding;
- deterministic replay;
- T0 / T1 / T2 evidence semantics;
- sealed honeypot ground truth;
- false-positive and critical-false-negative metrics;
- reviewer time saved;
- route roles and stages;
- causal-fragment closure evidence.

## 3. Compatibility matrix

| Invariant or field family | Identity spine | Route domain | Disposition | Repository-contract justification |
|---|---:|---:|---|---|
| Candidate cannot self-approve | yes | yes | reuse | `docs/identity-proposal-candidate.md` keeps a proposal distinct from approval; route candidates retain the same false authority-effects invariant. |
| Exact subject digest binding | yes | yes | reuse | `schemas/identity_proposal_candidate.example.json` binds proposal material; PR #772 supplies the route content digest and exact source HEAD. |
| Evidence and counterevidence preservation | yes | yes | adapt | `docs/identity-update-record.md` requires both support and counterevidence; route governance preserves typed workflow, replay, honeypot, and unavailable-provider refs instead of identity episodes. |
| Decision invalidated by material change | yes | yes | reuse | `docs/governance-handoff.md` separates reviewed material from the decision; the specimen invalidates on candidate, evidence, policy, or scope change. |
| Rollback / supersession without history rewrite | yes | yes | adapt | `docs/rollback-ledger.md` appends identity transitions; routes need their own immutable `RouteLedgerEntry` and supersession vocabulary. |
| Active-state reconstruction | yes | yes | adapt | `docs/identity-snapshot.md` reconstructs identity from governed records; `RouteRegistrySnapshot` reconstructs route state from route records and ledger entries. |
| Authority effects remain false at candidate stage | yes | yes | reuse | `docs/identity-proposal-candidate.md` requires all candidate authority effects to remain false; the route candidate repeats that closed list. |
| Continuity level | yes | no | adapt | `schemas/identity_proposal_candidate.example.json` carries identity continuity semantics; the shared envelope omits them rather than coercing them into route metadata. |
| Identity influence / profile patch | yes | no | adapt | `schemas/identity_update_record.example.json` is identity-specific; route durable state uses a typed `RouteVersionRecord` template instead. |
| Exact Git repository and HEAD | no | yes | route-only | PR #772's Route Artifact verifier binds the repository origin, ref, and exact commit for T0 evidence. |
| T0 / T1 / T2 evidence semantics | no | yes | route-only | PR #772 keeps deterministic replay, artifact-attested evidence, and narrative rejection-audit fields distinct. |
| Deterministic replay | no | yes | route-only | PR #772 binds replay inputs and output assertions to a replay-evidence digest. |
| Sealed honeypot evaluation | no | yes | route-only | PR #772 requires sealed ground truth and matching observed-result digests. |
| FP / FN / reviewer-time metrics | no | yes | route-only | PR #772 keeps route-effect metrics separate from identity influence and continuity fields. |
| Time / Space / Phase / Depth closure axes | no | yes | route-only | These are a deferred route causal-fragment pilot and have no checked-in identity-record equivalent. |

## 4. Shared governance envelope

A domain-neutral `GovernanceDecision` should bind to a typed subject without
pretending all subjects have the same payload:

```yaml
subjectKind: route_promotion_candidate
subjectRef: rpc_high-risk-code-review_2.0.0_001
subjectDigest: sha256:<candidate-digest>
evidenceSetDigest: sha256:<reviewed-evidence-set-digest>
decision: REQUEST_MORE_EVIDENCE
```

The same envelope may later bind to:

```yaml
subjectKind: identity_proposal_candidate
```

The decision envelope is shared. Candidate and durable-record schemas remain
domain-specific. `evidenceSetDigest` is the RFC 8785 JCS SHA-256 digest of the
specimen's closed `evidence_set_binding` object with its `digest` field set to
null. Candidate or evidence-set drift therefore invalidates the decision.
The specimen applies the same self-excluding convention to its other bindings:
canonicalize the complete object with its own `*_digest` field set to null,
then prefix the SHA-256 result with `sha256:`.

## 5. Independent truth authority

This is a mandatory governance invariant:

> The system whose behavior is being evaluated must not author, attest, or
> finalize the evidence that determines its own validity.

The executor may produce observed output, replay logs, and finding candidates.
It must not finalize:

- `confirmedEffectiveness`;
- `falsePositiveRate`;
- `reviewerMinutesSaved`;
- `sealed`;
- `groundTruthMatched`;
- `promotionEligible`;
- `maintainerApproved`;
- active `validated` state.
- `candidate_state` after governance has acted.

Those fields require an independent scorer, verifier, governance actor, or
registry projection.

## 6. Manual specimen result

The reference specimen lives at:

```text
examples/route-governance/route_governance_specimen_v0_1.json
```

It uses the evidence from PR #772 at exact HEAD:

```text
61216069d60c3cfe68c975ff2385d0d53339525c
```

The specimen intentionally ends with:

```text
GovernanceDecision = REQUEST_MORE_EVIDENCE
RouteVersionRecord.creation_status = not_created
RouteLedgerEntry.creation_status = not_created
```

Although this candidate selects T0, its `tier_semantics.boundaries` object also
round-trips the distinct T1 artifact/sign-off fields and T2 narrative/rejection
fields. T1 cannot contribute confirmed metrics or training eligibility; T2 is a
rejection audit and cannot enter the canonical route-evidence store.

This is the correct result because the checked-in T0 fixture has:

- one T0 run rather than twenty;
- one repository rather than two;
- one task variant rather than two;
- no confirmed-effectiveness confidence interval;
- no maintainer approval.

A complete specimen does not have to end in approval. The `not_created` objects
are non-record templates: their identifiers, digests, and timestamps remain
null, and they are excluded from registry reconstruction. They document the
fields a later approving decision would populate without fabricating durable
promoted state while evidence is below the promotion floor.

## 7. PR #772 boundary

PR #772 contains valuable route-specific evidence machinery:

- exact-head source binding;
- replay evidence integrity;
- T0 / T1 / T2 boundaries;
- sealed honeypots;
- deterministic tests;
- immutable lineage checks.

It must not silently establish a second generic governance stack.

Recorded disposition: **option 1 — merge PR #772 only as a narrow route-evidence
contract**, after its own current exact-head CI and independent review gates
pass. Its T0/T1/T2, replay, honeypot, digest, and immutable-lineage machinery
remains route-specific evidence. This PR owns the shared-envelope compatibility
decision; PR #772 must not add a generic governance lifecycle or treat route
evidence as action authority.

PR #772 remains Draft until those exact-head gates pass. This disposition does
not itself approve, merge, or validate that PR.

## 8. CausalFragment boundary

Do not build generic causal-graph tooling yet.

First encode one real manual causal fragment after the route-governance boundary
is accepted. It must include:

- Time / Space / Phase / Depth closure axes;
- an explicit swiss-cheese boundary path;
- AND / OR alternative-path search after the intervention;
- evidence tier on every causal edge;
- counterfactual verification and `verifyingTrail`;
- immutable supersession.

Generic tooling remains blocked until at least one route is honestly promoted
with T0 evidence.

## 9. Decision rule

Promote Option B to accepted architecture when the manual specimen demonstrates:

1. no route-specific evidence is silently lost;
2. candidate and decision digests are exactly bound;
3. self-approval and self-authored confirmed truth are impossible;
4. durable state is absent after a non-approving decision;
5. active route state can be reconstructed without trusting self-declared
   `validated` status;
6. route memory grants no action authority.

If a later implementation proves a clean normative generic substrate, Option A
may supersede this decision. Until then, shared principles and a shared decision
envelope are safer than forced type unification.
