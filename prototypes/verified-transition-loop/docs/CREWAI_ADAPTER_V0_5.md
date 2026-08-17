# VTL v0.5 — CrewAI-shaped Deferred Authorization Adapter

This adapter is a **compatibility reference**, not a CrewAI runtime plugin.

It is aligned with the `GuardrailProvider` / `BeforeToolCallHook` discussion in `crewAIInc/crewAI#4877`, including the later `suspend/defer -> resolve` and use-time execution-binding discussion.

## Why the adapter returns DEFER first

VTL separates historical authorization from permission to execute:

```text
historical validity
-> current admissibility
-> execution-bound authorization
```

Therefore an initial VTL `AUTHORIZE` maps to a CrewAI-shaped `DEFER`, not to `ALLOW`.

```text
GuardrailRequest
-> VTL authorization
-> DEFER
-> resume at the pre-tool execution boundary
-> fresh use-time revalidation
-> ALLOW | DENY
```

Only the resumed path may return `ALLOW`, and only after VTL emits a valid single-use `EXECUTE` receipt.

## Request shape

`CrewGuardrailRequest` mirrors the proposal's useful fields without importing CrewAI:

```text
tool_name
tool_input
agent_role
task_description
crew_id
timestamp
tool_call_id
```

`tool_call_id` is preferred as the execution-occurrence identity. `timestamp` is accepted as a fallback. If neither exists, the adapter denies with:

```text
OCCURRENCE_ID_MISSING
```

## Decision shape

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

`execution_binding` is currently:

```text
external
```

That is deliberate. The adapter can verify and consume a reference use token, but it cannot claim atomicity with CrewAI's actual tool side effect without a native runtime integration.

## Async approval

If the first VTL authorization is `HOLD`, the adapter returns `DEFER`.

On `resume(...)`, it resolves the current context again and performs a **fresh authorization decision**. Only after that decision becomes `AUTHORIZE` does it perform use-time revalidation.

This models:

```text
HOLD
-> external approval/evidence arrives
-> fresh AUTHORIZE
-> use-time revalidation
-> ALLOW
```

A previous `HOLD` is never treated as latent authority.

## Continuation binding

A continuation is bound to the exact serialized CrewAI-shaped request.

Changing tool arguments, tool identity, role, task, crew, timestamp, or tool-call occurrence prevents reuse:

```text
REQUEST_BINDING_MISMATCH
```

After a continuation successfully releases the tool once, reusing it fails:

```text
CONTINUATION_ALREADY_USED
```

## VTL v0.4 interoperability proof

`tests/test_crewai_adapter.py` runs the same nine v0.4 use-time vectors through this CrewAI-shaped adapter.

Expected mapping:

```text
VTL EXECUTE -> CrewAI-shaped ALLOW
VTL BLOCK   -> CrewAI-shaped DENY
```

The adapter preserves the same ordered VTL reason codes for denied use-time cases.

The vectors cover:

```text
stable context
source drift
policy drift
approval identity drift
evidence-context drift
approval revocation
approval expiry
executor substitution
missing execution nonce
```

The stable path also proves that one continuation cannot release the same tool twice.

## Non-claims

v0.5 does **not** claim:

- that CrewAI has adopted this interface;
- that this adapter is imported by CrewAI;
- that CrewAI exposes an atomic revalidate-and-execute primitive;
- that the in-memory pending/consumption stores are production durable;
- that `ALLOW` executes any real tool;
- that VTL grants external authority.

A production integration would need a native hook/continuation seam and durable atomic consumption at the real tool-execution boundary.
