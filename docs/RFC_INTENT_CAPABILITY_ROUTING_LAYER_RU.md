# RFC: Intent / Capability Routing Layer (ICRL)

## Статус
- Draft
- Версия: 0.1
- Scope: LS multi-agent architecture

## 1. Контекст

Текущий стек LS уже формирует сильную вертикаль исполнения:

`Agents → Decisions (CEL) → Models (MEL) → Events (CEM) → Ledger (CTL) → Memory (LTP)`

Скрытый риск масштабирования этой схемы — точка маршрутизации вызовов между агентами. Если каждый агент знает, кого именно вызывать, граф зависимостей растёт как `O(N²)` и требует ручной оркестрации.

## 2. Проблема

При жёстких агент-агент связях:
- добавление нового агента требует изменения существующих маршрутов;
- снижается эволюционная гибкость экосистемы;
- orchestration становится узким местом и вручную сопровождаемым кодом.

## 3. Предложение: ICRL

Добавить слой **Intent / Capability Routing Layer (ICRL)** между агентами и вычислительной экономикой.

### Принцип

Агент больше не выбирает конкретного исполнителя напрямую.

Он публикует интент (например: `forecast oil price`), а ICRL подбирает оптимальных исполнителей по capability-индексу и текущим ограничениям.

## 4. Базовый поток

`Agent → Intent → Capability Index → Matching Engine → Best Agents → Execution`

## 5. Capability Index (минимальный контракт)

Каждый агент публикует capability-профиль:

- `agent_id`
- `capability`
- `confidence`
- `price`
- `latency`
- `reputation`

Пример:

```yaml
agent_id: agent_A
capability: macro_forecasting
confidence: 0.81
price: 2_credits
latency: 350_ms
reputation: 0.92
```

## 6. Matching Engine (v1)

Для каждого интента роутинг использует композицию факторов:

1. **Semantic Match** — близость интента и capability.
2. **Reputation Filter** — отсечение нестабильных/недостоверных исполнителей.
3. **Price / Latency Optimization** — выбор Pareto-оптимального набора.

Возможная scoring-функция:

`score = w_sem * semantic + w_rep * reputation + w_conf * confidence - w_price * cost - w_lat * latency`

## 7. Архитектурный эффект

### До ICRL

- `N` агентов
- примерно `N²` явных связей

### После ICRL

- `N` агентов
- примерно `N` регистраций capability
- динамическая маршрутизация в runtime

Итог: переход от статически оркестрируемой сети к self-organizing topology.

## 8. Capability Market (следующий слой)

ICRL соединяется с CEL и формирует рынок навыков:

`capability → demand → price`

Это даёт:
- автоматическое перераспределение задач;
- экономику вкладов (contribution economy);
- incentive-механику для повышения качества capability.

## 9. Пример динамического pipeline

Intent: `predict earthquake risk Turkey`

ICRL может автоматически собрать pipeline:
- `geology_agent`
- `satellite_agent`
- `seismic_model`
- `risk_evaluator`

Сборка делается на основе capability matching и policy-ограничений, а не хардкода маршрутов.

## 10. Обновлённая целевая архитектура LS

`Agents → Intent Layer → Capability Market → Decision Economy → Model Economy → Event Mesh → Ledger → Memory`

## 11. MVP-план внедрения

### Phase 1 — Registry + Discovery
- Ввести `CapabilityRegistry` с CRUD capability-профилей.
- Определить `IntentEnvelope` и `CapabilityDescriptor` схемы.
- Добавить базовый matcher (semantic + hard filters).

### Phase 2 — Runtime Routing
- Встроить ICRL в current agent runtime как sidecar-модуль.
- Добавить fallback-стратегии (degraded mode при пустой выдаче).
- Включить трассировку `intent → candidate set → selected set` в CEM/CTL.

### Phase 3 — Economic Loop
- Подключить динамические веса цены/репутации из CEL.
- Ввести contribution scoring на основе фактических outcome-метрик.
- Сохранить reputation-traces в LTP для долгосрочного калибровочного цикла.

## 12. Метрики успеха

- `routing_success_rate` (доля интентов с валидным планом исполнения)
- `median_time_to_match`
- `execution_cost_per_intent`
- `multi_agent_composition_rate`
- `new_agent_time_to_first_task`

## 13. Риски и ограничения

- Semantic drift capability-описаний без нормализованной онтологии.
- Риск «игры» репутации без anti-abuse политик.
- Дополнительная latency на этапе route-planning.

Минимальные контрмеры:
- versioned capability schema;
- reputation provenance + signed traces в ledger;
- latency budgets и policy-based shortcuts для high-priority intent.

## 14. Почему это стратегически важно

ICRL устраняет главный bottleneck масштабирования multi-agent систем: ручную маршрутизацию между агентами.

В результате LS эволюционирует из набора интеграций в **самоорганизующуюся сеть коллективного интеллекта**, где discovery, кооперация и экономический стимул встроены в архитектуру.
