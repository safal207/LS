# Web4 Runtime Session Lifecycle Hooks

Web4 Runtime now supports lifecycle hooks for session state transitions:

- `onsessionopen(session_id)`
- `onsessionclose(session_id)`
- `onheartbeattimeout(session_id)`

## Event order guarantees

For timeout-driven failures, the runtime emits:

1. `onheartbeattimeout(session_id)`
2. `onsessionclose(session_id)`

For reconnect:

1. `onsessionopen(session_id)`

## Python usage

```python
from modules.web4_runtime.observability import ObservabilityHub
from modules.web4_runtime.rtt import RttConfig, RttSession

hub = ObservabilityHub()
session = RttSession[str](
    config=RttConfig(session_id=42, heartbeat_timeout_s=0.5),
    observability=hub,
)

session.register_on_session_open(lambda sid: print("open", sid))
session.register_on_session_close(lambda sid: print("close", sid))
session.register_on_heartbeat_timeout(lambda sid: print("timeout", sid))

session.disconnect()
session.reconnect()
```

## Observability integration

`RttSession` records lifecycle events to `ObservabilityHub` (if provided):

- `session_open`
- `session_close`
- `heartbeat_timeout`

Each event payload contains `session_id` and optional metadata (e.g. close reason).


Registering `onsessionopen` on an already connected session triggers the callback immediately.
