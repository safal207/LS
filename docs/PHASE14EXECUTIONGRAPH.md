# Phase 14 Execution Graph

```text
collective_state -> arbitration(score) -> execution_order
execution_order -> agent.step(context-native)
agent outputs -> shared_causal merge -> signal distribution -> next tick
```

## Determinism guarantees

- Stable tie-breaker по `agent_id`.
- Barrier sync: все агенты получают единый `prior_collective`.
- Execution order сохраняется в `collective_state["execution_order"]`.
