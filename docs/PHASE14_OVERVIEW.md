# Phase 14 — Deterministic Multi-Agent Synchronization

Phase 14 добавляет детерминированный глобальный цикл, где:

- **Synergy** определяет коллективное выравнивание и общее давление цели.
- **Militocracy** определяет дисциплину и приоритет исполнения.
- **GlobalTickCoordinator** строит стабильный порядок выполнения на каждом тике.

## Новые компоненты

- `GlobalTickCoordinator`
- `MultiAgentContext`
- `SynergyMilitocracyArbitrationLayer`
- `DeterministicSignalBus`

## Основная формула

```text
score(agent) =
  0.4 * synergy.collectivealignmentscore +
  0.3 * militocracy.discipline_score +
  0.2 * militocracy.ideaqualityscore +
  0.1 * synergy.sharedgoalpressure
```

## Поведение по тикам

1. Снимается `collective_state`.
2. Координатор вычисляет `execution_order`.
3. Агенты выполняют `step()` строго по этому порядку.
4. Сигналы и агрегаты публикуются после барьера тик-обновления.

Militocracy `override_signal` добавляет управляемый буст приоритета в арбитраже.
