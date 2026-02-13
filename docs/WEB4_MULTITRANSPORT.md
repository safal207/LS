# Web4 Runtime Multi-Transport Abstraction (Priority 6.3)

This step introduces a transport abstraction layer so runtime sessions are no longer bound directly to RTT internals.

## New core pieces

- `TransportBackend` protocol: unified transport contract (`connect`, `disconnect`, `send`, `receive`, `pending`, `stats`, `heartbeat`, `check_heartbeat_timeout`).
- `RttTransport`: adapter that implements `TransportBackend` on top of existing `RttSession`.
- `TransportRegistry`: factory registry for selecting transport backends by name.
- `Web4Session`: transport-agnostic session wrapper that delegates delivery to selected backend and records transport-level observability events.

## Migration path

- Existing code using `RttSession` directly remains valid.
- New transport-agnostic path:

```python
registry = TransportRegistry[str]()
registry.register("rtt", lambda: RttTransport(RttSession[str]()))
transport = registry.create("rtt")
session = Web4Session[str](transport=transport)
```

## Observability

`Web4Session` emits transport-layer events with `transport_type` payload for unified cross-transport telemetry.
