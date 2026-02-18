# Phase 14.7: Global Flow Controller

This phase introduces `GlobalFlowController` in `python/modules/web4_runtime/flow.py`.

## Goals
- Centralized global pressure accounting across sessions.
- Support fixed and proportional per-session gating.

## Components
- `BackpressureStrategy = Literal["fixed", "proportional"]`
- `GlobalFlowController`
  - `register_session` / `unregister_session`
  - `on_enqueue` / `on_dequeue` / `on_reset`
  - `wait_for_available_space_sync` / `wait_for_available_space`
  - `can_enqueue`

## Policy
- `fixed`: use `per_session_limit` directly.
- `proportional`: use `min(per_session_limit, total_limit // active_sessions)`.


## Sequence (send success)

```text
Session.send -> local max_queue check -> GlobalFlowController.try_enqueue -> queue append
```

## Sequence (send local overflow)

```text
Session.send -> local max_queue reached -> overflow policy handler (dropoldest/dropnewest/block/error)
```

## Sequence (send global overflow)

```text
Session.send -> local queue has room -> GlobalFlowController.try_enqueue=False -> overflow policy handler
```

## DropOldest Swap Semantics

- DropOldest replacement is modeled as `dequeue(old) -> enqueue(new)`.
- When a message is evicted, global counters are decremented first (`on_dequeue`).
- Replacement message must pass global admission (`try_enqueue`) before local enqueue.
- Net effect for a successful swap is zero delta in `total_pending`.

## Session Lifecycle Rules

- `register_session` / `unregister_session` are explicit lifecycle boundaries.
- Non-weakref session objects are retained strongly until `unregister_session` is called.
- `managed_session(session)` is available as a context-manager helper to guarantee unregister on exit.
- `can_enqueue` is side-effect free and does not auto-register unknown sessions.

## Space Notifications

- `on_dequeue` and `on_reset` emit free-space notifications.
- Notifications are exposed for both sync waiters and async waiters (`notify_available_space`).
- Async notifications are dispatched through a controller-owned `asyncio.Event`.
- Async waiters use a notification epoch (`current_space_epoch`) to avoid missed wakeups.
- Sync waiters use `wait_for_available_space_sync(..., after_epoch=...)` to wake on global free-slot without timeout polling.
