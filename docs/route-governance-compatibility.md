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

| Invariant or field family | Identity spine | Route domain | Disposition |
|---|---:|---:|---|
| Candidate cannot self-approve | yes | yes | reuse |
| Exact subject digest binding | yes | yes | reuse |
| Evidence and counterevidence preservation | yes | yes | reuse |
| Decision invalidated by material change | yes | yes | reuse |
| Rollback / supersession without history rewrite | yes | yes | reuse |
| Active-state reconstruction | yes | yes | reuse principle |
| Authority effects remain false at candidate stage | yes | yes | reuse |
| Continuity level | yes | no | identity-only |
| Identity influence / profile patch | yes | no | identity-only |
| Exact Git repository and HEAD | no | yes | route-only |
| Deterministic replay | no | yes | route-only |
| Sealed honeypot evaluation | no | yes | route-only |
| FP / FN / reviewer-time metrics | no | yes | route-only |
| Time / Space / Phase / Depth closure axes | no | yes | route-only pilot |

## 4. Shared governance envelope

A domain-neutral `GovernanceDecision` should bind to a typed subject without
pretending all subjects have the same payload:

```yaml
subjectKind: route_promotion_candidate
subjectRef: rpc_high-risk-code-review_2.0.0_001
subjectDigest: sha256:<candidate-digest>
decision: REQUEST_MORE_EVIDENCE
```

The same envelope may later bind to:

```yaml
subjectKind: identity_proposal_candidate
```

The decision envelope is shared. Candidate and durable-record schemas remain
domain-specific.

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
RouteVersionRecord = null
RouteLedgerEntry = null
```

This is the correct result because the checked-in T0 fixture has:

- one T0 run rather than twenty;
- one repository rather than two;
- one task variant rather than two;
- no confirmed-effectiveness confidence interval;
- no maintainer approval.

A complete specimen does not have to end in approval. It has to prove that the
system refuses to fabricate durable promoted state when evidence is below the
protocol floor.

## 7. PR #772 boundary

PR #772 contains valuable route-specific evidence machinery:

- exact-head source binding;
- replay evidence integrity;
- T0 / T1 / T2 boundaries;
- sealed honeypots;
- deterministic tests;
- immutable lineage checks.

It must not silently establish a second generic governance stack.

Before merge, record one of these dispositions:

1. merge a narrow route-evidence contract;
2. reshape around the shared governance envelope described here; or
3. split route evidence from route governance.

Until then PR #772 remains Draft under `ARCHITECTURE_HOLD`.

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
