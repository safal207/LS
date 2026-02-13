# Web4 Runtime Session Lifecycle Hooks

This document reflects the current Python runtime behavior in `python/modules/web4_runtime/rtt.py`.

## Hook API (current names)

Use explicit register/unregister methods:

- `register_on_session_open(hook)`
- `register_on_session_close(hook)`
- `register_on_heartbeat_timeout(hook)`
- `unregister_on_session_open(hook)`
- `unregister_on_session_close(hook)`
- `unregister_on_heartbeat_timeout(hook)`
- `clear_session_hooks()`

Legacy names like `onsessionopen` are obsolete and should not be used.

## Event ordering guarantees

For heartbeat timeout flow, ordering is deterministic:

1. `heartbeat_timeout`
2. `session_close` (with `reason="heartbeat_timeout"`)

For reconnect flow:

1. `session_open` (with reconnect metadata)

For manual disconnect flow:

1. `session_close` (with `reason="manual"` by default)

## Smart-hook behavior

- Registering `register_on_session_open` on an already connected session invokes the hook immediately.
- Hook recursion is guarded by an internal emission guard (`_emitting`) to prevent nested re-entrant callback loops.

## Python usage

```python
from modules.web4_runtime.observability import ObservabilityHub
from modules.web4_runtime.rtt import RttConfig, RttSession

hub = ObservabilityHub()
session = RttSession[str](
    config=RttConfig(session_id=42, heartbeat_timeout_s=0.5),
    observability=hub,
)

def on_open(sid: int) -> None:
    print("open", sid)

def on_close(sid: int) -> None:
    print("close", sid)

def on_timeout(sid: int) -> None:
    print("timeout", sid)

session.register_on_session_open(on_open)
session.register_on_session_close(on_close)
session.register_on_heartbeat_timeout(on_timeout)

session.unregister_on_session_close(on_close)
session.register_on_session_close(on_close)

session.disconnect()
session.reconnect()
session.clear_session_hooks()
```

## Observability event names

`RttSession` records lifecycle events to `ObservabilityHub`:

- `session_open`
- `session_close`
- `heartbeat_timeout`

Each payload includes `session_id` and optional metadata (`reason`, `reconnects`, etc.).
