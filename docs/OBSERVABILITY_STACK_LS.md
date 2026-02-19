**Версия:** 0.3 (готов к коммиту)
**Дата:** 18 февраля 2026
**Автор:** Главный архитектор LS

### 1. Назначение

Определить **внутренний** observability stack LS без внешних платформ, с closed-loop:
**сбор → анализ → корреляция → human-reviewed предложение → feedback → re-run**.

### 2. Что уже есть в LS

- **ObservabilityHub** — центральный хаб.
- **RttStats + GlobalFlowController** — детальные метрики.
- **Hexagon Core** — reasoning-ядро.
- **AdaptiveGovernor** — runtime-тюнинг.
- **AgentLoop + Shadow Layer** — цикл observe-think-act-verify.
- **Web4 Runtime** — распределённый транспорт.

### 3. Архитектура (Mermaid)

```mermaid
graph LR
    subgraph "LS Application & Runtime"
        A[AgentLoop + Shadow Layer] -->|events + traces| B[ObservabilityHub]
        C[Web4 Runtime RTT] -->|rtt stats + flow metrics| B
        D[GlobalFlowController] -->|backpressure + rejection| B
        E[Hexagon Core] -->|reasoning traces| B
        F[AdaptiveGovernor] -->|tuning actions| B
    end

    subgraph "Observability Plane (внутренний)"
        B --> G[Persistent Store]
        G --> H[Internal Query Interface]
    end

    subgraph "Closed Loop Reasoning"
        K[ObservabilityHub] -->|query + correlate| L[Hexagon Core + Shadow Layer]
        L -->|analyze + reason| M[AdaptiveGovernor]
        M -->|propose change (human approval required)| N[AgentLoop]
        N -->|apply + restart| O[Workload Re-run]
        O -->|new metrics + feedback| K
    end

    B -->|correlate reason| K
```

### 4. Ключевые изменения (по вашим замечаниям)

- **Query Engine**: один **Internal Query Interface** (минимальный subset PromQL для метрик + простой text search для логов + trace-id lookup для трейсов). Полноценные LogQL/PromQL/TraceQL — out of scope на Phase 15-16.
- **Auto-PR / propose change**: явно **human-in-the-loop approval** + safety gates (canary deploy, rollback, manual review перед применением). Автоматический PR исключён.
- **OTLP-подобный**: заменено на **OTLP-compatible exporter** (полная совместимость с OpenTelemetry Protocol).

### 5. Источники данных

- AgentLoop + Shadow Layer: reasoning logs, tool calls, HCP feedback.
- Web4 Runtime: RTT, queue pressure, Merit deltas, Synergy proofs.
- Hexagon Core: Beliefs Graph diffs, causality events.
- GlobalFlowController + AdaptiveGovernor: backpressure, reject-rate, limit adjustments.

### 6. Минимальный план реализации (Phase 15–16)

1. OTLP-compatible exporter в Rust и Python (3–4 дня).
2. Расширить ObservabilityHub до Internal Query Interface (5–7 дней).
3. Замкнуть loop с human-in-the-loop approval.
4. Добавить сквозную trace correlation по trace-id.

### 7. Definition of Done

- Все ключевые компоненты публикуют OTLP-compatible телеметрию.
- Работает единая корреляция по trace-id.
- AdaptiveGovernor выполняет минимум один тюнинг с human approval.
- Workload re-run фиксирует measurable improvement.
