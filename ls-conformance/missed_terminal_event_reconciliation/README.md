# missed_terminal_event_reconciliation

## Purpose

Prove that an external client can recover from a missed terminal event without relying on resume as a correctness primitive.

This fixture family targets agent runtimes where a turn reaches terminal state server-side, but the external client misses the live terminal notification because of compaction, reconnect, stream interruption, or transport loss.

## Core invariant

A push-only terminal lifecycle state is not sufficient for external recovery.

If a client can miss `turn/completed` or an equivalent terminal event, the runtime must provide a bounded reconciliation path:

1. detect a gap in the notification stream;
2. reconnect or re-open the client session;
3. pull authoritative terminal turn state;
4. converge without replaying side effects or using resume as the truth oracle.

## Minimal contract

- monotonic notification sequence on `turn/*` and/or `thread/*` notifications;
- authoritative terminal-state pull, such as `thread/read` or `get_turn_state(thread_id, turn_id)`;
- bounded convergence after reconnect;
- no duplicate terminal side effects.

## Accept vectors

- terminal event missed, sequence gap detected, terminal state pulled successfully;
- client state converges to committed server state;
- no duplicate action, tool call, publish, or resume side effect occurs;
- terminal status remains queryable after reconnect.

## Reject vectors

- terminal state exists only as a push notification;
- reconnect succeeds but client cannot determine whether the turn completed;
- client must call `thread/resume` merely to discover the turn was already terminal;
- duplicate side effects occur during recovery;
- sequence gap cannot be detected.

## Canonical scenario

```text
client connected
  ↓
compaction / stream interruption
  ↓
server commits terminal turn state
  ↓
client misses terminal notification
  ↓
client detects sequence gap
  ↓
client pulls authoritative terminal state
  ↓
client converges without resume or duplicate effects
```

## Upstream mapping

- Codex external JSON-RPC clients
- compaction / reconnect paths
- terminal event delivery bugs
- runtime reconciliation protocol design

## LS issue

Canonical pack: https://github.com/safal207/LS/issues/757
