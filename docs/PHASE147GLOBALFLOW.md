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
