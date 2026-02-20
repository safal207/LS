# Web4 Federation Policy (Phase 7.0)

This document defines the initial federation policy contract and enforcement path in Web4 Runtime.

## Scope

Current implementation is in:

- `python/modules/web4_runtime/federation_policy.py`
- `python/modules/web4_runtime/protocol_router.py`
- `python/modules/web4_runtime/agent_integration.py`

## Policy contract

`FederationPolicy` is a runtime interface:

```python
class FederationPolicy(Protocol):
    def evaluate(self, envelope: Dict[str, Any]) -> FederationDecision: ...
```

`FederationDecision` fields:

- `allowed: bool`
- `reason: str`
- `policy: str`

## Built-in policies

- `AllowAllFederationPolicy`
  - default policy;
  - always returns `allowed=True`.

- `DenylistFederationPolicy`
  - blocks by sender, receiver, and/or message type;
  - evaluation order:
    1. blocked message type,
    2. blocked sender,
    3. blocked receiver,
    4. allow.

## Enforcement point

Enforcement happens in `Web4ProtocolRouter.dispatch()` before protocol-router and trust transitions:

1. `policy.evaluate(envelope)`
2. if denied:
   - return `handled=False`
   - skip protocol handler and trust mutation
3. if allowed:
   - proceed with `ProtocolRouter.dispatch()`
   - proceed with CIP trust handling

## Observability contract

`AgentLoopAdapter.handle_envelope()` emits federation fields in both returned payload and observability events:

- `federation_allowed`
- `federation_reason`
- `federation_policy`

This is required for diagnostics in cross-domain routing scenarios.

`ObservabilityHub.federation_metrics()` provides aggregate counters for federation decisions:

- `total`, `allowed`, `denied`, `allow_ratio`
- `by_policy`
- `denied_by_reason`

Rolling and export helpers:

- `ObservabilityHub.federation_metrics_window(window_size=...)` for last-N decision slices.
- `ObservabilityHub.export_federation_metrics(window_size=...)` for diagnostics/CI payload export.

## Usage examples

Default (allow all):

```python
router = Web4ProtocolRouter(cip=cip, hcp=hcp, lip=lip)
```

Deny HELLO for selected sender:

```python
from modules.web4_runtime.federation_policy import DenylistFederationPolicy

policy = DenylistFederationPolicy.from_iterables(
    blocked_senders=["agent-a"],
    blocked_message_types=["HELLO"],
)
router = Web4ProtocolRouter(cip=cip, hcp=hcp, lip=lip, federation_policy=policy)
```

## Test coverage

Core tests:

- `python/tests/test_web4_federation_policy.py`
- `python/tests/test_web4_runtime.py` (router enforcement + adapter behavior + observability fields + federation metrics aggregation/export)
- `python/tests/test_web4_interoperability.py` (mesh/graph contract checks)

## Merge DoD checklist

- [ ] Denied envelopes do not mutate trust state.
- [ ] Denied envelopes do not reach `AgentLoop` handler/output queue.
- [ ] Observability payload includes all federation fields.
- [ ] `test_web4_federation_policy.py` is green.
- [ ] `test_web4_runtime.py` is green.
- [ ] `test_web4_interoperability.py` is green.
- [ ] `web4_runtime_ci` runs federation policy tests.

## Next incremental steps

- Add allowlist and domain-scope policy variants.
- Add policy composition (AND/OR chains).
- Add policy metrics sink adapters (Prometheus/OpenTelemetry).
