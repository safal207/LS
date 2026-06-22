# LS Trusted Cooperative Runtime — Contract Architecture

Status: **v0.1 foundation draft**  
Parent issue: [#591](https://github.com/safal207/LS/issues/591)  
Epic: [#599](https://github.com/safal207/LS/issues/599)

## Purpose

The Trusted Cooperative Runtime turns temporary multi-agent work into an
inspectable cooperation artifact:

```text
task
-> plan and roles
-> route
-> causal audit
-> evidence decision
-> authorization
-> commit-before-effect execution
-> replay and persistence
-> reusable artifact
```

This document defines boundaries and provider-neutral contracts. It does not
claim that all ecosystem integrations are implemented.

## Ownership boundaries

| Layer | Owns | Does not own |
| --- | --- | --- |
| LS | workflow continuity, shared contracts, trail assembly, adapter sequence | provider internals or hidden model reasoning |
| DAO_lim | model/backend route selection and route explanation | task intent or execution authorization |
| CML | causal-lineage audit | workflow planning |
| PythiaLabs | evidence sufficiency decision | performing the side effect |
| ProofPath | portable intent and authorization evidence | deciding which model should run |
| CaPU | commit-before-effect execution control | evidence generation |
| LTP | deterministic path inspection and replay | durable event storage |
| LiminalDB | append-only event persistence | semantic interpretation of the workflow |

Integrations must be implemented through adapters. LS must not copy the
internal implementation of these repositories into its core.

## Canonical contract family

The first checked-in contracts are:

- `TaskEnvelope`: original intent, actor, trail, time, and evidence references.
- `RoleAssignment`: provider-neutral capability assignment with a parent cause.
- `WorkflowStep`: bounded action, dependencies, role, evidence, and causal parent.
- `WorkflowPlan`: one task plus its roles and ordered work graph.
- `EvidenceDecision`: `ALLOW`, `HOLD`, `BLOCK`, or `ESCALATE` with evidence.
- `ExecutionAuthorization`: scoped, expiring, nonce-bearing permission derived from `ALLOW`.
- `ReusableArtifact`: references to routes, evidence, contributions, decision, execution, and replay.

Schemas live under:

```text
schemas/trusted_runtime/
```

Python contracts and adapter protocols live under:

```text
python/modules/trusted_runtime/
```

## Required identity and lineage fields

Where applicable, records carry:

- `task_id`: stable identity of the user-visible task;
- `trail_id`: stable identity of the full cooperation trail;
- `parent_cause`: the task, delegation, decision, or prior step that justifies the record;
- `actor`: human, adapter, model, service, or gate responsible for the record;
- timestamp fields;
- `evidence_refs`: references rather than embedded private payloads.

## Validation layers

Validation is deliberately split:

1. **JSON Schema validation** checks shape, required fields, versions, enums, and closed objects.
2. **Python semantic validation** checks relationships that JSON Schema cannot reliably express, such as:
   - unique role and step identifiers;
   - role references that resolve;
   - causal parents that exist;
   - dependencies that resolve;
   - prevention of self-parent and self-dependency links;
   - execution permission only from an `ALLOW` decision.

A record is not accepted merely because it is valid JSON.

## Safety invariants

The v0.1 contracts establish these invariants:

1. Every workflow step has an explicit parent cause.
2. Every workflow step references a declared role.
3. `ALLOW` requires inspectable evidence before it can become authorization.
4. Execution authorization is scoped, expiring, and nonce-bearing.
5. `HOLD`, `BLOCK`, and `ESCALATE` are decisions, not execution permissions.
6. Model output is a proposal and never authorizes a side effect by itself.
7. Provider-specific fields remain behind adapter boundaries.
8. Secret values and private payloads must not be copied into reusable artifacts.

## Versioning

The initial versions are intentionally narrow:

```text
trusted_runtime.workflow_plan.v0.1
trusted_runtime.evidence_decision.v0.1
trusted_runtime.execution_authorization.v0.1
trusted_runtime.reusable_artifact.v0.1
```

Breaking changes require a new version. Adapters should reject unknown major or
contract versions rather than silently guessing.

## Local validation

Run the focused contract tests:

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_contracts.py
```

The fixtures include one valid workflow and negative examples for missing
causal ancestry, an unknown role reference, and authorization without evidence.

## Non-goals for v0.1

- no live model calls;
- no Fugu-specific dependency;
- no cloud or multi-tenant service;
- no real payment, deploy, merge, or destructive action;
- no claim of production completeness;
- no automatic write into personal long-term memory;
- no formal proof of complete safety.

## Next step

After these contracts are reviewed, [#592](https://github.com/safal207/LS/issues/592)
can implement the deterministic provider-neutral workflow orchestrator against
this contract surface.
