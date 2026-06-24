# Agent Lifecycle Reliability Conformance v0.1

Status: **local deterministic LS reference contract**

## Purpose

This suite turns recurring agent-runtime failure modes into portable, reviewable conformance cases:

```text
orphaned agent registry
bounded close timeout
lost terminal event
reconnect and replay
duplicate delivery
stale connection generation
```

The suite is motivated by public Codex reports including:

- openai/codex#19197 — persistent orphaned subagents;
- openai/codex#24389 — `close_agent` blocking for hours;
- openai/codex#28495 — server-side completion without client terminal notification;
- openai/codex#14722 — one thread observed across multiple clients.

It does not claim to reproduce Codex internals. It defines vendor-neutral lifecycle invariants that any agent runtime can test.

## Core invariants

```text
not visible != terminated
termination requested != termination confirmed
server completed != subscriber observed completion
event published != event acknowledged
reconnect != permission to accept stale-generation events
```

More precisely:

1. A registry entry with no live runtime must be reconciled before its resource slot is trusted.
2. A live runtime with no registry entry must be quarantined rather than silently adopted.
3. Closing an unresponsive child must return within a configured hard timeout.
4. Repeated close requests are idempotent for terminal children.
5. A lost terminal event must be replayable from an acknowledged sequence cursor.
6. Duplicate terminal delivery must not create duplicate completion.
7. Events from superseded connection generations must be rejected.

## Fixture format

Each line in `fixtures/agent-lifecycle-reliability/cases.jsonl` is one independent case conforming to:

```text
schemas/agent_lifecycle_case_v0_1.schema.json
```

The deterministic reference validator is:

```text
tools/validate_agent_lifecycle_reliability_v0_1.py
```

Run locally:

```bash
python tools/validate_agent_lifecycle_reliability_v0_1.py
```

Expected output is a JSON report with all cases passing.

## Operation model

### `ORPHAN_RECONCILE`

Compares durable registry state with observed runtime state.

```text
registry says RUNNING + runtime MISSING
  -> stale registry
  -> release slot after reconciliation

registry MISSING + runtime RUNNING
  -> orphan runtime
  -> quarantine; do not release or trust slot accounting
```

### `CLOSE_AGENT`

Models bounded shutdown behavior.

```text
graceful close
  -> grace timeout
  -> hard-timeout escalation
  -> terminal receipt
  -> parent returns
```

The parent must not remain blocked after the hard timeout.

### `STREAM_RECONCILE`

Models ordered lifecycle delivery with cursor replay, deduplication, and generation fencing.

```text
live stream
  -> event dropped
  -> reconnect from last acknowledged sequence
  -> replay missing event
  -> rebuild client projection
```

An event is accepted only when:

- its connection generation equals the active generation;
- its delivery is not marked `DROPPED`;
- its `event_id` has not already been accepted.

## Honest boundary

This suite proves only the behavior of the checked-in deterministic reference model.

It does **not** claim:

- integration with Codex or any other vendor runtime;
- distributed exactly-once delivery;
- operating-system process termination guarantees;
- universal recovery from arbitrary storage corruption;
- authority to execute actions merely because lifecycle state was recovered.

Lifecycle recovery, memory continuity, and event delivery never imply execution authorization.

## Related LS work

- Causal audit: issue #594
- Evidence gates: issue #595
- Commit-before-effect: issue #596
- Deterministic replay: issue #597
- Recovered continuation envelope: PR #651
