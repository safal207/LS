# Verified Transition Loop (VTL) v0.6

VTL treats the **verified state transition**, not the agent, as the primary unit of execution.

```text
Intent
  -> Transition Proposal
  -> Evidence Gate
  -> AUTHORIZE | HOLD | BLOCK
  -> use-time revalidation
  -> EXECUTE | BLOCK
  -> separately authorized executor
  -> Observed Outcome
  -> invariant verification
  -> COMMIT | RETRY | ROLLBACK | ESCALATE
```

## Core invariants

- verifier and executor are distinct;
- historical authorization/alignment is not execution authority;
- current source/policy/approval/evidence/executor state is revalidated immediately before use;
- a valid `EXECUTE` receipt is occurrence-bound and single-use;
- mission-version drift fails closed rather than silently reinterpreting the goal;
- recovery is a new verified transition rather than implicit mutation authority;
- observed outcome remains separate from the pre-action verdict.

VTL itself does not deploy software, execute framework tools, merge code, change IAM, send messages, make payments, use credentials, or grant external authority.

## Why v0.6 matters

v0.6 proves that the same use-time contract can be mapped onto two different agent-framework shapes without standardizing either framework's internal classes or storage model:

```text
VTL semantic oracle
        |
        +-> CrewAI-shaped deferred tool authorization
        |
        +-> AutoGen-shaped Mission Keeper transition gate
```

Both adapters are dependency-free reference layers. They do **not** claim native framework integration or upstream adoption.

## CrewAI-shaped adapter (v0.5)

Artifacts:

```text
src/verified_transition_loop/crewai_adapter.py
docs/CREWAI_ADAPTER_V0_5.md
tests/test_crewai_adapter.py
```

Lifecycle:

```text
GuardrailRequest
-> VTL authorization
-> DEFER | DENY
-> continuation / external approval
-> fresh authorization when prior state was HOLD
-> use-time revalidation
-> ALLOW | DENY
```

A VTL `AUTHORIZE` maps to `DEFER`, never directly to `ALLOW`.

Only `resume(...)` may return `ALLOW`, and only after use-time revalidation produces a valid, single-use `EXECUTE` receipt.

Continuation safety:

```text
mutated request             -> REQUEST_BINDING_MISMATCH
wrong continuation token    -> CONTINUATION_TOKEN_INVALID
successful continuation x2  -> CONTINUATION_ALREADY_USED
```

The adapter reports:

```text
execution_binding = external
```

because it cannot claim atomicity with a real CrewAI tool side effect.

## AutoGen-shaped Mission Keeper adapter (v0.6)

Artifacts:

```text
src/verified_transition_loop/autogen_adapter.py
docs/AUTOGEN_ADAPTER_V0_6.md
tests/test_autogen_adapter.py
```

Historical assessment and use-time control are separate records:

```text
MissionTransitionRequest
        ↓
MissionIntegrityRecord
        ↓
use-time revalidation
        ↓
CONTINUE | HALT | REQUIRE_REVIEW
```

`MissionIntegrityRecord.assessment = ALIGNED` is historical evidence only. It is not an execution permit.

The adapter intentionally exposes no executor, repair, rewrite, or task-mutation API.

Verifier/executor separation is mechanical:

```text
same verifier + executor -> VERIFIER_EXECUTOR_NOT_SEPARATED
```

Mission reinterpretation is version-bound:

```text
mission version changes after assessment
-> MISSION_VERSION_CHANGED
-> HALT
```

A historical `HOLD` carries no latent authority. When new approval/evidence arrives, the adapter performs a fresh authorization before the use-time gate.

Outcome separation remains explicit:

```text
MissionIntegrityRecord
        ↓
MissionOutcomeLink
        ↓
MissionObservedOutcome
```

The observed result cannot rewrite the historical pre-action verdict.

## Vendor-neutral use-time conformance (v0.4)

The portable semantic oracle remains:

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
src/verified_transition_loop/conformance.py
```

Normative across implementations:

- `AUTHORIZE != EXECUTE`;
- exact source/policy/approval/evidence/executor comparison at use time;
- ordered reason codes;
- non-empty execution occurrence nonce;
- single-use execution-permit consumption.

Implementation-local:

```text
receipt IDs
storage keys
signing envelopes
trace IDs
database rows
framework-native object identities
```

Reference vectors:

```text
stable context              -> EXECUTE
source changed              -> BLOCK
policy changed              -> BLOCK
approval identity changed   -> BLOCK
evidence context changed    -> BLOCK
approval revoked            -> BLOCK
approval expired            -> BLOCK
executor substituted        -> BLOCK
execution nonce missing     -> BLOCK
```

Cross-runtime mapping:

```text
stable context              -> EXECUTE / CrewAI ALLOW / AutoGen CONTINUE
source changed              -> BLOCK   / DENY         / HALT
policy changed              -> BLOCK   / DENY         / HALT
approval identity changed   -> BLOCK   / DENY         / HALT
evidence context changed    -> BLOCK   / DENY         / HALT
approval revoked            -> BLOCK   / DENY         / HALT
approval expired            -> BLOCK   / DENY         / HALT
executor substituted        -> BLOCK   / DENY         / HALT
execution nonce missing     -> BLOCK   / DENY         / HALT
```

Denied framework-shaped cases preserve the same ordered VTL reason codes.

Run the vendor-neutral profile:

```bash
python -m pip install -e .
vtl-conformance fixtures/use-time-conformance-v0.4.json
```

## Use-time execution receipt

`revalidate_authorization_for_use()` produces an integrity-verifiable receipt containing:

```text
authorization_decision_id
transition_id
EXECUTE | BLOCK
executor_id
proposal_digest
context_digest
execution_nonce
checked_at_ms
```

Changes fail closed with reason codes such as:

```text
SOURCE_REF_CHANGED
POLICY_REF_CHANGED
APPROVAL_REF_CHANGED
EVIDENCE_CONTEXT_CHANGED
APPROVAL_NOT_CURRENT_AT_USE
APPROVAL_EXPIRED_AT_USE
EXECUTOR_BINDING_MISMATCH
EXECUTION_NONCE_INVALID
```

The reference `UseTokenRegistry` demonstrates first-use success and replay rejection. It is an in-memory conformance reference, not a production distributed replay store.

## Post-action verification

`verify_executed_outcome()` carries both proof layers forward:

```text
AuthorizationReceipt
        +
UseTimeReceipt
        +
ObservedOutcome
        ↓
COMMIT | RETRY | ROLLBACK | ESCALATE
```

A tampered or blocked use-time receipt cannot produce `COMMIT`.

## Deployment transition demo

The deterministic demo is side-effect-free and covers:

```text
healthy:
AUTHORIZE -> EXECUTE -> simulated deploy -> COMMIT

failure/recovery:
AUTHORIZE -> EXECUTE -> health failure -> ROLLBACK
-> AUTHORIZE recovery -> EXECUTE recovery -> COMMIT

TOCTOU:
AUTHORIZE under policy v1
-> policy changes before execution
-> BLOCK
-> execution_performed = false
```

Run:

```bash
vtl-deployment-demo
```

## Exact-head CI

Dedicated workflow:

```text
.github/workflows/verified-transition-loop-v0.6.yml
```

It is path-scoped and read-only:

```text
permissions: contents: read
checkout.persist-credentials: false
```

The workflow:

- validates machine-readable contracts;
- installs the isolated package;
- verifies package version `0.6.0`;
- runs the complete focused suite;
- runs all nine vendor-neutral vectors;
- verifies the side-effect-free deployment / rollback / TOCTOU demo.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Current boundary

v0.6 is a reference protocol, simulation oracle, vendor-neutral conformance fixture, and two framework-shaped compatibility adapters.

It has:

- no native CrewAI dependency;
- no native AutoGen dependency;
- no claim of framework adoption;
- no production deployment adapter;
- no GitHub write capability inside VTL;
- no cloud API or IAM capability;
- no credential access;
- no payment capability;
- no automatic merge path;
- no durable distributed use-token or continuation registry.

A production framework integration must own the real execution boundary, persist continuation/consumption state durably, and consume the execution permit atomically enough that stale or already-used authority cannot produce a second side effect.
