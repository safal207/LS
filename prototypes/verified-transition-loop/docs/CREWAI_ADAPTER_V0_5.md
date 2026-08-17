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

## Request and occurrence shape

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

The resolved occurrence is stored with pending continuation state. A resumed request must reproduce the same serialized request and therefore the same occurrence identity.

After one successful `ALLOW`, the occurrence is marked released for the lifetime of the reference adapter instance. Repeating the initial `evaluate()` for the same occurrence cannot recreate fresh single-use authority:

```text
OCCURRENCE_ALREADY_RELEASED
```

A repeated `evaluate()` while the occurrence is still pending is idempotent: it returns the existing decision and continuation rather than replacing pending state.

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

## Continuation security and binding

A continuation is bound to the exact serialized CrewAI-shaped request.

Changing tool arguments, tool identity, role, task, crew, timestamp, or tool-call occurrence prevents reuse:

```text
REQUEST_BINDING_MISMATCH
```

Continuation tokens are generated with cryptographically strong randomness and stored only in pending adapter state. They are **not derivable** from `decision_ref`, the request digest, or occurrence id. Resume checks the supplied token with constant-time `secrets.compare_digest()`.

A forged or incorrect token fails with:

```text
CONTINUATION_TOKEN_INVALID
```

After a continuation successfully releases the tool once, reusing it fails:

```text
CONTINUATION_ALREADY_USED
```

## VTL v0.4 interoperability proof

The portable v0.4 oracle now contains ten vectors, including an explicit proposal/transition-drift case.

`tests/test_crewai_adapter.py` maps the framework-applicable use-time vectors through the CrewAI-shaped adapter. The portable proposal override is exercised directly by the core oracle because this adapter constructs its proposal from the bound request; request mutation is covered separately by `REQUEST_BINDING_MISMATCH`.

Expected semantic mapping remains:

```text
VTL EXECUTE -> CrewAI-shaped ALLOW
VTL BLOCK   -> CrewAI-shaped DENY
```

The adapter preserves ordered VTL reason codes for denied use-time cases that reach the portable revalidation layer.

## Reference-state boundary

The pending-continuation map, released-occurrence set, and use-token registry are in-memory reference mechanisms. They demonstrate the normative idempotency and single-use rules but are not a durable distributed transaction system.

A production integration must persist continuation and occurrence-consumption state durably and make permit consumption atomic enough with the actual tool dispatch that retries or concurrent workers cannot produce a second side effect.

## Non-claims

v0.5 does **not** claim:

- that CrewAI has adopted this interface;
- that this adapter is imported by CrewAI;
- that CrewAI exposes an atomic revalidate-and-execute primitive;
- that the in-memory pending/consumption stores are production durable;
- that `ALLOW` executes any real tool;
- that VTL grants external authority.

A production integration would need a native hook/continuation seam and durable atomic consumption at the real tool-execution boundary.
