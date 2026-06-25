# Temporal Relationship Semantics Fixtures v0.1

## Purpose

This profile defines portable, engine-neutral semantics for typed relationship
edges in agent memory systems. It is motivated by `mem0ai/mem0#5440`, where
flat entity-to-memory links cannot express why entities are connected or whether
a relationship is still current.

The profile is intentionally narrower than LS Relational Temporal Orientation
Center (RTOC):

- this profile resolves raw typed edges;
- RTOC evaluates a full relational trajectory before coordinated continuation.

## Core boundary

> Relationship memory may describe context and history. It does not create
> mutuality, consent, permission, truth, or execution authority.

All results therefore carry all-false authority effects:

```json
{
  "may_authorize_execution": false,
  "may_establish_consent": false,
  "may_establish_mutuality": false,
  "may_establish_truth": false,
  "may_grant_permissions": false
}
```

## Edge envelope

Each edge identifies:

- source and target entities;
- typed relation and directionality;
- private, group, or global scope;
- lifecycle status;
- `valid_from` / `valid_until` temporal bounds;
- assertion, confirmation, evidence, and ratification provenance;
- semantic weight;
- supersession and scope-promotion references.

Lifecycle states are:

```text
CLAIMED / RATIFIED / DISPUTED / SUPERSEDED / EXPIRED / REVOKED
```

## Normative invariants

1. A co-mention is not a relationship.
2. One participant's assertion cannot establish mutual friendship or consent.
3. Historical truth does not imply current validity.
4. A future-dated edge is neither current nor historical before `valid_from`.
5. Revoked or expired delegation remains auditable but inactive.
6. A revoked edge for one target does not poison a distinct, independently ratified current target.
7. Supersession preserves history without making old and new states current.
8. Cardinality-one contradictions produce `CONFLICTED`, never last-write-wins.
9. A disputed edge cannot be returned as settled current context.
10. A weak mention cannot downgrade a stronger ratified relationship in the same visible scope.
11. Private edges cannot be promoted to broader scopes without explicit authority.
12. Every `RATIFIED` edge requires an explicit ratification reference.
13. Supersession references must resolve to an older `SUPERSEDED` edge with the same source and relation type.
14. Even a current ratified delegation edge does not authorize execution at the memory layer.

## Temporal classification

The evaluator classifies matching edges into three disjoint sets:

- `current` — `valid_from <= now`, not expired/revoked/superseded, and not past `valid_until`;
- `historical` — expired, revoked, superseded, or past `valid_until`;
- `future` — `valid_from > now`.

Future edges are suppressed from current results and produce
`RELATIONSHIP_NOT_YET_VALID` when no current or historical edge is available.
They must never be mislabeled as history.

## Resolution precedence

For the queried source entity and relation type:

1. classify current, historical, and future edges;
2. reject current unauthorized scope promotion;
3. preserve revoked authority history, rejecting only when no valid current authority-sensitive edge exists or when revocation conflicts with the same target;
4. choose the first visible scope from explicit query precedence;
5. abstain on disputed winners;
6. suppress mention-only evidence when stronger substantive evidence exists;
7. prefer ratified evidence over weaker claims for the same target;
8. enforce reciprocity for mutual relations;
9. detect cardinality-one contradictions;
10. return current context or a clearly labeled claim while retaining history.

## Decisions

- `RETURN_CURRENT` — ratified relationship context is current.
- `RETURN_CLAIM` — a current unratified claim may be returned as a claim.
- `RETURN_HISTORICAL` — relationship evidence is valid history but not current.
- `CONFLICTED` — current exclusive edges disagree.
- `ABSTAIN` — mutuality, provenance, temporal readiness, or settled state is insufficient.
- `REJECT` — a hard boundary such as revoked delegation, revocation conflict, or unauthorized scope promotion is violated.

## Fixture suites

The profile freezes thirteen cases across five digest-pinned suites:

### Friendship

- mention does not create `friend_of`;
- unilateral friendship does not become mutual;
- mutually confirmed friendship becomes current context only;
- a later co-mention cannot downgrade an already ratified friendship.

### Temporal history

- former employment remains historical;
- a new manager edge supersedes the old edge without deleting history;
- a future employment edge is not returned as historical before its start time.

### Authority-sensitive relationships

- revoked delegation is rejected when it is the only relevant delegation state;
- active delegation is still non-authoritative memory context;
- revoked delegation to one target does not poison a separate active target.

### Conflict and dispute

- two current managers for a cardinality-one relation are conflicted;
- disputed trust produces abstention.

### Scope

- private friendship cannot silently become global relationship state.

## Run

```bash
python tools/run_temporal_relationship_semantics_fixtures.py
```

The command:

1. verifies the pinned SHA-256 fixture set;
2. validates every suite against Draft 2020-12 JSON Schema with date-time format checks;
3. validates ratification, supersession references, and disjoint result classifications;
4. evaluates all vectors deterministically;
5. emits:

```text
artifacts/temporal-relationship-semantics-conformance.json
```

## Mapping to memory frameworks

A framework can adopt the contract incrementally.

For entity-to-memory links, relation metadata may be stored alongside each link:

```json
{
  "memory_id": "mem-1",
  "relation_type": "employer_of",
  "semantic_weight": 1.0,
  "status": "RATIFIED",
  "valid_from": "2024-01-01T00:00:00Z",
  "valid_until": null,
  "evidence_refs": ["contract-1"]
}
```

For entity-to-entity relationships, the same fields can live in a dedicated
edge collection. Storage engines, embeddings, graph traversal, and extraction
models are deliberately out of scope. The conformance boundary is the semantic
result, not the backend.

## Non-goals

This profile does not:

- decide universal truth;
- infer consent from conversational tone;
- grant roles, capabilities, permissions, or delegation;
- execute tools;
- prescribe a universal relationship ontology;
- replace human or policy review for sensitive relationships.
