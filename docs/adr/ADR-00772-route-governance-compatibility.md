# ADR: Route governance compatibility — reuse identity spine or share only the governance envelope?

## Status

**Proposed compatibility probe.**

PR `#772` remains Draft. This ADR freezes architecture expansion while one manual T0 specimen is evaluated. It does not declare a normative cross-domain schema or a production registry runtime.

## Context

Route Artifact v2 currently combines route definition, evidence, promotion policy, lifecycle status, maintainer approval, immutable lineage, and registry projection in one contract.

LS already describes an identity-governance topology with separate stages:

```text
IdentityProposalCandidate
  -> governance decision
  -> durable identity update record
  -> rollback / supersession history
  -> reconstructed identity snapshot
```

The topology is relevant, but compatibility is not yet proven:

| Claim | Evidence state |
|---|---|
| Shared governance topology exists | demonstrated in design notes and identity handoff contracts |
| Normative cross-domain candidate schema exists | not demonstrated |
| Universal shared registry runtime exists | not demonstrated |
| Route-specific T0/T1/T2 evidence contract exists | implemented in PR #772 |
| Identity examples are normative schemas | false; the examples explicitly say they are reference-only |

Equal topology does not imply equal domain semantics. `IdentityProposalCandidate` carries identity influence, continuity level, actor/relationship scope, profile mutation, and trait semantics. Route promotion carries task profile, agent roles, exact Git HEAD, deterministic replay, false-positive and critical-false-negative evidence, sealed honeypots, reviewer time, and route alternatives.

## Decision

Use **one shared governance envelope and shared lifecycle invariants**, while retaining **domain-specific candidates, durable records, and projections** unless a later specimen proves stronger compatibility.

```text
IdentityProposalCandidate ----\
                                -> GovernanceDecision
RoutePromotionCandidate -------/
                                -> domain-specific durable record
                                -> shared ledger principles
                                -> domain-specific projection
```

Do not model `RoutePromotionCandidate` as `IdentityProposalCandidate`.

Do not treat current `RouteArtifact.status` or `metrics.maintainer_approved` as proof of the final generic lifecycle architecture. During this Draft PR they remain compatibility-bound fields in the existing narrow verifier contract; external candidate/decision separation is the target boundary.

## Shared invariants

| Invariant | Identity spine | Route domain |
|---|---:|---:|
| Candidate cannot approve itself | reuse | reuse |
| Decision binds exact subject digest | reuse | reuse |
| Proposer and approver are separated | reuse | reuse |
| Evidence and counterevidence survive decision | reuse | reuse |
| Approved history is not silently rewritten | reuse | reuse |
| Rollback and supersession create new records | reuse | reuse |
| Current state is reconstructed from ordered history | reuse | reuse |
| Memory grants no action authority | reuse | reuse |

## Domain-only semantics

| Identity-only | Route-only |
|---|---|
| continuity level | exact Git HEAD |
| identity/profile influence | deterministic replay |
| actor and relationship scope | T0/T1/T2 evidence tiers |
| trait candidate / profile mutation | sealed honeypots |
| identity revalidation semantics | false-positive and critical-false-negative metrics |
| identity application and rollback contracts | reviewer time saved and causal route evidence |
|  | alternative AND/OR route search |

## Reference flow for the probe

```text
RouteEvidenceBundle
  -> RoutePromotionCandidate
  -> GovernanceDecision
  -> RouteVersionRecord
  -> RouteLedgerEntry
  -> RouteRegistrySnapshot
```

The manual reference specimen is:

`examples/route-governance/route-governance-t0-manual-specimen.json`

It deliberately requests only `experimental` registration because the current fixture has one T0 run, one repository, one task variant, no confidence intervals, and no independently recorded maintainer decision. It must not project `candidate` or `validated`.

## Digest boundary

A governance decision must bind the exact canonical digest of the candidate it reviewed:

```yaml
subject_kind: route_promotion_candidate
subject_ref: route-candidate://...
subject_digest: sha256:...
decision: approve | reject | quarantine | more_evidence
```

Changing the candidate, evidence set, requested state, scope, exact HEAD, or rollback/supersession data invalidates the decision binding.

The candidate does not contain its own approval, validated status, or action authority.

## Projection boundary

The durable record links evidence and the external governance decision:

```yaml
RouteVersionRecord:
  route_ref: route://...
  evidence_ref: route-evidence://...
  governance_decision_ref: decision://...
```

The active state is computed later:

```yaml
RouteRegistrySnapshot:
  active_state: experimental
  active_version_ref: route-version://...
```

A snapshot is disposable projection data. Deleting and rebuilding it from the ordered ledger must produce the same active state.

## Scope freeze for PR #772

Until the specimen is reviewed, do not add:

- a CausalFragment execution engine;
- a universal graph registry;
- additional lifecycle states;
- marketplace behavior;
- route or model rankings;
- a generic candidate framework;
- a generic registry runtime.

The current T0/T1/T2 verifier, exact-head binding, deterministic replay, honeypot evidence, canonical digest, adversarial tests, immutable lineage checks, and critical false-negative boundaries remain valuable and in scope.

## Manual acceptance checks

1. T0 replay, exact-head, metrics, and honeypot evidence remain reachable without governance state being copied into the evidence bundle.
2. `GovernanceDecision.subject_digest` exactly matches the canonical `RoutePromotionCandidate`.
3. The proposing actor cannot be the deciding actor.
4. A later supersession creates a new candidate, decision, durable record, and ledger events without modifying the old record.
5. Removing the snapshot and replaying the ledger reconstructs the same active route version and state.
6. No record grants merge, deploy, execution, tool, memory-write, or other protected action authority.

## Follow-up decision

After the specimen, choose one outcome:

### A — high compatibility

Extract shared normative contracts such as `GovernedCandidate`, `GovernanceDecision`, `VersionedUpdateRecord`, `LifecycleLedgerEntry`, and `RegistrySnapshot`.

### B — partial compatibility (expected)

Share only the decision envelope, exact-digest binding, rollback/supersession principles, and projection rules. Keep route and identity schemas domain-specific.

### C — weak compatibility

Keep independent domain contracts. Document the same governance invariants and enforce them with conformance tests rather than shared types.

## Consequences

### Positive

- prevents self-attested route validation;
- preserves the strong route-specific evidence work in PR #772;
- reuses mature governance principles without identity-semantic leakage;
- keeps rollback, supersession, and reconstruction auditable;
- avoids a nullable cross-domain “super schema”.

### Cost

- introduces an explicit candidate/decision/record boundary;
- requires one compatibility specimen before generic tooling;
- may leave some current Route Artifact lifecycle fields transitional until the final split is implemented.
