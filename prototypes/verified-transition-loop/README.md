# Verified Transition Loop (VTL) v0.3

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

## Core invariant

**The verifier cannot be the executor of the transition it verifies.**

v0.3 adds a second boundary:

> **`AUTHORIZE` is not an execution token.**

An authorization only says that the proposed transition was acceptable at evaluation time. Immediately before execution, VTL revalidates the current source, policy, approval, evidence, executor, and approval lifetime.

Only a fresh `EXECUTE` use-time receipt may cross the execution boundary.

VTL itself does not deploy software, merge code, change IAM, send messages, make payments, use credentials, or grant external authority.

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

v0.2 bound the post-action result to the pre-action authorization receipt. v0.3 closes the remaining TOCTOU window before the action occurs.

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
```

A use-time receipt is integrity-verifiable and bound to a non-empty execution occurrence nonce.

## Single-use execution permit

The reference `UseTokenRegistry` demonstrates one more property:

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
python -m pip install -e .
vtl-deployment-demo
```

Representative output:

```text
healthy.use_time              = EXECUTE
healthy.deploy                = COMMIT
health_failure.deploy         = ROLLBACK
health_failure.rollback       = COMMIT
pre_execute_drift.use_time    = BLOCK
pre_execute_drift.execution   = false
ledger_valid                  = true
external_side_effects         = false
```

## Deterministic evidence

Authorization, use-time, outcome, and recovery receipts use canonical JSON plus SHA-256.

The append-only evidence ledger records:

```text
intent
proposal
authorization
use-time revalidation
execution-permit consumption
observed outcome
outcome verdict
recovery transition
recovery use-time revalidation
recovery outcome
```

The full chain can be replay-verified for tampering.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

Current focused suite:

```text
30 passed
```

## Current boundary

v0.3 is still a reference protocol and simulation oracle.

It has:

- no production deployment adapter;
- no GitHub write capability;
- no cloud API or IAM capability;
- no credential access;
- no payment capability;
- no automatic merge path;
- no durable distributed use-token registry.

A real executor must remain separately authorized, pin the exact VTL implementation, consume the use token atomically with the protected side effect, and be independently reviewed.
