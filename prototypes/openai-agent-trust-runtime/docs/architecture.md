# Architecture

## Design goal

Add verifiable delegation and authority boundaries around an OpenAI Agents SDK workflow without replacing the SDK runner, handoffs, sessions, or tracing.

## Component map

```text
User goal
  │
  ▼
OpenAI Agents SDK Runner
  │
  ├── Coordinator Agent
  ├── Developer Agent
  ├── QA Agent
  └── Safety Reviewer
          │
          │ typed handoff callbacks
          ▼
LS Agent Trust Runtime
  ├── DispatchReceipt registry
  ├── ResultReceipt registry
  ├── Recovery / supersession lineage
  ├── Human Approval registry
  ├── Protected Effect policy
  └── Append-only hash-chained ledger
```

## Core records

### DispatchReceipt

Binds:

- parent agent;
- child agent;
- exact task;
- constraints;
- proposed authority scope;
- sequence;
- optional superseded dispatch.

The authority scope means **what the agent may propose for later evaluation**. It is not a credential and is never sufficient by itself to execute an effect.

### ResultReceipt

Binds:

- exact dispatch;
- exact child agent;
- terminal status;
- digest of the result summary;
- evidence references.

Only the named child can submit the result. `COMPLETED` without evidence is rejected.

### ApprovalReceipt

Binds:

- exact dispatch;
- exact protected effect;
- human approver label;
- reason.

The current prototype records the receipt but does not authenticate the human. Production work would replace the label with a signed identity-provider assertion.

### EffectDecision

Evaluates whether:

1. the dispatch exists and is current;
2. the result belongs to that dispatch;
3. the result is completed;
4. the effect is inside the declared scope;
5. a protected effect has a separate human approval.

`allowed=true` is a policy result, not execution.

## OpenAI Agents SDK integration

The integration uses typed `handoff()` callbacks. Each callback receives model-generated bounded metadata through a Pydantic `DispatchInput`:

```text
task
constraints[]
requested_authority[]
```

Before the receiving specialist takes over, the callback writes an LS dispatch receipt. The Agents SDK remains responsible for model turns, handoffs, tool calls, and tracing.

## Recovery

A replacement agent does not overwrite the original task. It receives a new dispatch with:

```text
new_dispatch.supersedes = interrupted_dispatch.receipt_id
```

The old dispatch becomes stale and cannot accept a terminal result or authorize an effect. This prevents a late response from a crashed or partitioned agent from winning a race against the recovered worker.

## Ledger integrity

Every runtime event is stored with:

```text
offset
previous_hash
event_type
payload
record_hash
```

The hash chain detects mutation, deletion, insertion, and reordering inside the observed record sequence. It does not provide external timestamping or signer identity in v0.1.

## Deliberate non-goals

- replacing OpenAI tracing;
- deciding whether model content is factually correct;
- executing external effects;
- storing secrets or credentials;
- authenticating human identity;
- solving distributed consensus;
- claiming production readiness.

## Next technical increment

The smallest valuable v0.2 would add:

1. SQLite persistence with transaction boundaries;
2. signed human approvals;
3. verified evidence artifacts, not string references;
4. OpenTelemetry correlation with OpenAI trace and span IDs;
5. a durable queue and idempotency key for effect adapters;
6. one forced-crash integration test across two worker processes.
