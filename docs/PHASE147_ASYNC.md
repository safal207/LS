# Phase 14.7: Async RTT Runtime

This phase introduces `AsyncRttSession` in `python/modules/web4_runtime/async_rtt.py`.

## Goals
- Async-first send/receive API for Web4 RTT.
- Preserve semantics of sync backpressure modes (`error`, `dropoldest`, `dropnewest`, `block`).
- Keep compatibility with existing `RttConfig` / `RttStats`.
- Supports optional `GlobalFlowController` admission control.

## API
- `send_async(message, priority=None)`
- `receive_async()`
- `wait_message(timeout_s=...)`
- `disconnect()` / `reconnect()`
- `heartbeat()` / `check_heartbeat_timeout()`

## Notes
- Queue semantics are shared with sync RTT via `modules.web4_runtime.rtt_queue.RttQueue`.
- Uses `asyncio.Condition` (no busy-spin loops).
- Disconnect notifies waiters to unblock blocked producers/consumers.
- Global admission waits are synchronized via `GlobalFlowController.wait_for_available_space(...)`.
- After successful dequeue, async sessions call `flow_controller.notify_available_space()` to wake global waiters.
- Global wait path uses `current_space_epoch` + `after_epoch` to prevent missed notify races.
- Block mode re-checks both global admission and local `max_queue` before enqueueing.
