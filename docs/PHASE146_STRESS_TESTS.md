# Phase 14.6 Stress Testing Framework

## QoS Policy Stress Tests

Покрыты сценарии:

- `dropoldest`
- priority queue ordering under load
- failover recovery latency

## Performance Budgets

| Metric | Budget | Critical |
|---|---:|---:|
| `volatility_computation_time_ns` | < 1000ns | > 5000ns |
| `priority_queue_insert_time_ns` | < 500ns | > 2000ns |
| `failover_detection_time_ms` | < 100ms | > 500ms |
| `failover_recovery_time_sec` | < 5s | > 30s |
