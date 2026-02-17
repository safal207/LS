# Phase 14 Execution Graph

```text
collective_state -> prepare_tick(arbitration score) -> execution_order
execution_order -> agent.step(context-native)
agent outputs -> shared_causal merge -> signal distribution -> next tick
```

## Determinism guarantees

- Stable tie-breaker по `agent_id`.
- Barrier sync: все агенты получают единый `prior_collective`.
- Execution order сохраняется в `collective_state["execution_order"]`.


- DeterministicSignalBus limits per-tick processing via `max_signals_per_tick` to avoid runaway re-entrancy loops.
