# Verified Transition Loop (VTL) v0.5

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
- `AUTHORIZE` is not execution authority;
- current source/policy/approval/evidence/executor state is revalidated immediately before execution;
- a valid `EXECUTE` receipt is single-use;
- recovery is a new verified transition rather than implicit mutation authority.

VTL itself does not deploy software, merge code, change IAM, send messages, make payments, use credentials, or grant external authority.

## v0.5: CrewAI-shaped deferred authorization adapter

v0.5 adds the first framework-shaped compatibility layer:

```text
src/verified_transition_loop/crewai_adapter.py
docs/CREWAI_ADAPTER_V0_5.md
tests/test_crewai_adapter.py
```

It is aligned with the `GuardrailProvider` / `BeforeToolCallHook` discussion in `crewAIInc/crewAI#4877`, including the later `suspend/defer -> resolve` and use-time execution-binding discussion.

The adapter intentionally has **no CrewAI dependency** and does not claim native integration.

### CrewAI-shaped lifecycle

```text
GuardrailRequest
-> VTL authorization
-> DEFER | DENY
-> continuation / external approval
-> fresh authorization when prior state was HOLD
-> use-time revalidation
-> ALLOW | DENY
```

A VTL `AUTHORIZE` maps to `DEFER`, not directly to `ALLOW`:

```text
AUTHORIZE != EXECUTE
```

Only `resume(...)` may return `ALLOW`, and only when use-time revalidation produces a valid, single-use `EXECUTE` receipt.

### Request surface

`CrewGuardrailRequest` models:

```text
tool_name
tool_input
agent_role
task_description
crew_id
timestamp
tool_call_id
```

`tool_call_id` is preferred as the execution occurrence identity. `timestamp` is accepted as a fallback. If neither exists, the adapter denies with `OCCURRENCE_ID_MISSING`.

### Decision surface

The adapter emits:

```text
ALLOW | DEFER | DENY
reason_codes
decision_ref
continuation_token
execution_allowed
authorization_decision_id
use_id
execution_binding
```

`execution_binding` remains `external`: the reference adapter cannot claim atomicity with a real CrewAI tool side effect.

### Continuation safety

A continuation is bound to the exact CrewAI-shaped request. Mutating the request before resume yields:

```text
REQUEST_BINDING_MISMATCH
```

A continuation that already released the tool once cannot be reused:

```text
CONTINUATION_ALREADY_USED
```

If the first authorization was `HOLD`, resumed execution performs a **fresh authorization decision** before use-time revalidation. A prior `HOLD` never becomes latent authority.

## v0.4: vendor-neutral use-time conformance

The v0.4 interoperability profile remains the portable semantic oracle:

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
```

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

The v0.5 CrewAI-shaped adapter runs these same nine vectors and maps them as:

```text
VTL EXECUTE -> CrewAI-shaped ALLOW
VTL BLOCK   -> CrewAI-shaped DENY
```

Denied cases preserve the same ordered VTL reason codes.

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

The reference `UseTokenRegistry` demonstrates first-use success and replay rejection. It remains an in-memory conformance reference, not a production distributed replay store.

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

The deterministic side-effect-free demo still covers:

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

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Current boundary

v0.5 is a reference protocol, simulation oracle, vendor-neutral conformance fixture, and CrewAI-shaped compatibility adapter.

It has:

- no production deployment adapter;
- no native CrewAI runtime dependency;
- no claim of CrewAI adoption;
- no GitHub write capability inside VTL;
- no cloud API or IAM capability;
- no credential access;
- no payment capability;
- no automatic merge path;
- no durable distributed use-token or continuation registry.

A production framework integration must own the actual tool-execution boundary, persist continuation/consumption state durably, and consume the execution permit atomically enough that an already-used or stale permit cannot produce a second side effect.
