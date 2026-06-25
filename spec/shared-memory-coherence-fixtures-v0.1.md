# Shared-Memory Coherence Fixtures v0.1

## Purpose

This profile defines portable, engine-neutral fixtures for multi-agent shared
memory. It was motivated by the design questions in `microsoft/autogen#7748`,
but it does not prescribe AutoGen internals or require LS as a dependency.

The boundary under test is simple:

> Shared memory returns provenance-bound context. It does not create truth,
> consensus, approval, permission, or execution authority.

## Why this exists

A shared store makes collaboration easier, but it can also amplify one agent's
unsupported claim across an entire group. The dangerous transition is not the
write itself. It is the silent semantic upgrade performed by a later consumer:

```text
agent A wrote "the user approved deployment"
  -> group memory stored the sentence
  -> agent B recalled it
  -> agent B treated the sentence as human approval
```

The fixtures make that upgrade observable and testable.

## Normative invariants

- stored claim is not a ratified fact;
- shared is not universally true;
- repetition is not consensus;
- memory is not approval;
- memory is not permission;
- historical is not current;
- scope promotion requires explicit authorization;
- unresolved contradiction must not become last-write-wins;
- recall identifies which scope won and why;
- retrieval never authorizes execution.

## Decisions

- `RETURN_CLAIM`: return current context while preserving its unratified status.
- `RETURN_RATIFIED`: return reviewed context, still without authority effects.
- `CONFLICTED`: current same-scope values disagree and no resolution exists.
- `REJECT`: the memory transition itself violates a hard boundary.
- `ABSTAIN`: evidence is insufficient for the requested interpretation.

Every result carries all-false authority effects:

```json
{
  "may_authorize_execution": false,
  "may_establish_consensus": false,
  "may_establish_human_approval": false,
  "may_establish_truth": false,
  "may_grant_permissions": false
}
```

## Covered vectors

1. A single writer's group memory remains a claim.
2. Unauthorized `agent -> global` promotion is rejected.
3. Contradictory current claims become `CONFLICTED`.
4. Superseded history is retained but excluded from current selection.
5. Declared group-over-global precedence is visible in the receipt.
6. Human-approval text without `approval_ref` produces `ABSTAIN`.
7. Ratified capability context still grants no permission or execution authority.

## Run

```bash
python tools/run_shared_memory_coherence_fixtures.py
```

The command verifies the frozen SHA-256 pin, validates structural invariants,
evaluates every vector deterministically, and writes:

```text
artifacts/shared-memory-coherence-conformance.json
```

No network, model, database, or third-party dependency is required.

## Integration guidance

A runtime may map its native records to these fields and compare its result to
the expected envelope. Internal storage, indexing, embeddings, and prompting are
out of scope. Implementations remain free to use SQLite, vector stores, graph
stores, or remote services.

The important part is semantic parity at the boundary:

```text
write provenance -> current-state resolution -> bounded recall receipt
```

## Non-goals

This profile does not:

- decide whether a recalled statement is globally true;
- implement human approval;
- grant roles, permissions, capabilities, or delegation;
- authorize or execute tools;
- require consensus algorithms;
- define a universal ontology of relationships.
