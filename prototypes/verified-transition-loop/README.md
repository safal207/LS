# Verified Transition Loop (VTL) v0.4

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

**The verifier cannot be the executor of the transition it verifies.**

**`AUTHORIZE` is not an execution token.**

An authorization says only that the proposed transition was acceptable at evaluation time. Immediately before execution, VTL revalidates the current source, policy, approval, evidence, executor, and approval lifetime.

Only a fresh `EXECUTE` use-time receipt may cross the execution boundary.

Recovery is also modeled as a new verified transition rather than implicit mutation authority.

VTL itself does not deploy software, merge code, change IAM, send messages, make payments, use credentials, or grant external authority.

## v0.4: vendor-neutral use-time conformance

v0.4 turns the v0.3 use-time boundary into a portable interoperability profile.

The machine-readable artifacts are:

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
```

The fixture standardizes semantic behavior rather than one framework's classes or storage layout.

Normative across implementations:

- `AUTHORIZE != EXECUTE`;
- exact source/policy/approval/evidence/executor comparison at use time;
- `EXECUTE | HOLD | BLOCK` verdicts;
- ordered reason codes;
- non-empty execution occurrence nonce;
- single-use `EXECUTE` consumption.

Implementation-local:

```text
receipt IDs
storage keys
signing envelopes
trace IDs
database rows
```

This lets CrewAI, AutoGen, Codex-style runtimes, workflow engines, and custom agents use different internals while proving the same transition boundary.

## Reference conformance vectors

The v0.4 fixture includes nine cases:

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

The stable vector also proves exactly-once reference semantics:

```text
first consume of EXECUTE receipt -> true
same receipt replay              -> false
```

Run it:

```bash
python -m pip install -e .
vtl-conformance fixtures/use-time-conformance-v0.4.json
```

The runner exits `0` only when every vector matches its expected semantic result.

## Why use-time revalidation exists

Between:

```text
AUTHORIZE -> EXECUTE
```

the world can change.

Examples:

- the candidate commit moves;
- a policy is replaced;
- an approval is revoked or expires;
- evidence is refreshed or contradicted;
- a different executor attempts to consume the decision.

v0.2 bound the post-action result to the pre-action authorization receipt. v0.3 closed the TOCTOU window before the action. v0.4 makes that boundary independently testable outside this implementation.

## Authorization-time bindings

An authorization receipt binds:

- transition and intent identity;
- exact proposal digest;
- complete evidence digest;
- source reference;
- policy reference;
- approval reference and expiry;
- verifier identity;
- executor identity;
- final `AUTHORIZE | HOLD | BLOCK` verdict.

Missing source, policy, or approval references produce `HOLD`.

## Use-time receipt

`revalidate_authorization_for_use()` compares current execution context against the frozen authorization context.

A successful receipt contains:

```text
authorization_decision_id
transition_id
EXECUTE
executor_id
proposal_digest
context_digest
execution_nonce
checked_at_ms
```

Changes fail closed with explicit reasons such as:

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

## Single-use execution permit

The reference `UseTokenRegistry` demonstrates:

```text
valid EXECUTE receipt -> first consume succeeds
same receipt replay   -> rejected
```

The in-memory registry is a conformance reference, not a production distributed replay store. A production integration needs durable/transactional consumption at the real side-effect boundary.

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

Expected invariants are checked against independently observed post-state:

- all expected invariants hold and state matches -> `COMMIT`;
- failed invariant with rollback path -> `ROLLBACK`;
- failed invariant with retry-only path -> `RETRY`;
- missing evidence, invalid binding, or no safe recovery path -> `ESCALATE`.

## Deployment Transition Demo

The demo remains deterministic and **side-effect-free**.

Healthy path:

```text
AI proposes deploy(commit X)
  -> AUTHORIZE
  -> source/policy/approval/evidence revalidated
  -> EXECUTE
  -> simulated deploy
  -> independent observation
  -> COMMIT
```

Failure/recovery path:

```text
AUTHORIZE
  -> EXECUTE
  -> simulated deploy
  -> health invariant fails
  -> ROLLBACK
  -> rollback becomes a new verified transition
  -> AUTHORIZE rollback
  -> revalidate rollback at use time
  -> EXECUTE
  -> simulated restore
  -> recovery verification
  -> COMMIT
```

TOCTOU path:

```text
AUTHORIZE under policy v1
  -> policy changes to v2 before execution
  -> use-time revalidation
  -> BLOCK
  -> execution_performed = false
  -> production state unchanged
```

Run:

```bash
vtl-deployment-demo
```

## Deterministic evidence

Authorization, use-time, outcome, and recovery receipts use canonical JSON plus SHA-256 inside the reference implementation.

The v0.4 conformance profile deliberately does **not** require other implementations to share VTL's receipt-ID namespace. It tests the portable semantics first.

The append-only evidence ledger records intent, proposal, authorization, use-time revalidation, permit consumption, observed outcomes, recovery transitions, and recovery verification in one replay-verifiable chain.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Current boundary

v0.4 is still a reference protocol, simulation oracle, and interoperability fixture.

It has:

- no production deployment adapter;
- no GitHub write capability;
- no cloud API or IAM capability;
- no credential access;
- no payment capability;
- no automatic merge path;
- no durable distributed use-token registry;
- no claim that receipt IDs are globally interoperable.

A real executor must remain separately authorized, pin the exact VTL implementation, consume the use token atomically with the protected side effect, use a durable replay store, and be independently reviewed.
