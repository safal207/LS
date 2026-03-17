# ТЗ: Portfolio Flow Controller для AI Venture Engine

## 1. Цель

Реализовать управляемый контур **Portfolio Flow Controller (PFC)**, который ограничивает запуск проектов, концентрирует капитал и предотвращает деградацию доходности портфеля при росте числа валидированных идей.

Документ является техническим заданием на внедрение PFC в контур:

`Idea Engine → Validation Engine → Portfolio Flow Controller → Project Factory → Execution Network → Capital Allocator`.

## 2. Проблема и ожидаемый результат

### 2.1 Проблема

Система генерирует больше `validated_ideas`, чем может качественно исполнить:

- рост backlog;
- распыление treasury;
- частые реприоритизации агентной сети;
- низкая конверсия в проекты стадии scale.

### 2.2 Ожидаемый результат

После внедрения PFC:

1. запуск новых проектов ограничен capacity-aware политиками;
2. капитал концентрируется в проектах с наибольшим expected value;
3. слабые проекты закрываются быстрее (снижение kill latency);
4. улучшается conversion из validation в scale.

## 3. Scope

### 3.1 In Scope

- Admission control перед созданием проекта;
- Портфельные WIP-лимиты;
- Stage-gate политики переходов;
- Приоритизация бюджета через capital concentration policy;
- Portfolio метрики и алерты;
- Интеграция событий в Creation Ledger.

### 3.2 Out of Scope (v1)

- Полностью автономный запуск ad-кампаний;
- Мультифондовая стратегия с отдельными risk-профилями;
- RL-оптимизация allocation policy.

## 4. Термины и сущности

### 4.1 Сущности

- `IdeaObject` — гипотеза после генерации.
- `ValidationRecord` — результаты валидации (рынок, спрос, feasibility).
- `ProjectObject` — активный стартап в системе.
- `PortfolioState` — агрегированное состояние портфеля.
- `AllocationDecision` — решение о бюджете/заморозке/закрытии.
- `GateDecision` — решение `pass|hold|freeze|kill` по stage-gate.

### 4.2 Стадии проекта

- `incubation`
- `early_pmf`
- `scale`
- `frozen`
- `killed`

## 5. Функциональные требования

### FR-1 Admission Control

Система **обязана** вычислять `expected_value` до создания `ProjectObject`:

`expected_value = p_success * upside - required_capital - execution_risk_penalty`

#### Правила

- Создание проекта разрешено только если:
  - `expected_value >= dynamic_cutoff`,
  - есть свободный слот по WIP-лимиту,
  - treasury >= minimum_runway(project_type).

### FR-2 WIP-Limits

Система **обязана** поддерживать конфигурируемые лимиты:

- `max_active_projects_total`
- `max_active_projects_incubation`
- `max_active_projects_scale`

При превышении лимита новые проекты переводятся в очередь `admission_queue`.

### FR-3 Stage-Gate Engine

Система **обязана** выполнять gate-проверку при:

- завершении validation;
- плановом weekly review;
- резком ухудшении ключевой метрики (event-triggered).

#### Ворота

- **Gate A (problem-solution fit)**: `signup_rate`, `CAC_proxy`, `time_to_MVP`.
- **Gate B (early PMF)**: `activation_rate`, `retention_d7`, `retention_d30`.
- **Gate C (scale)**: `LTV_CAC`, `payback_period`, `gross_margin`.

### FR-4 Capital Concentration

Система **обязана** перераспределять бюджет по policy:

- top-tier проекты получают 60–80% execution budget;
- проектам в uncertainty-tier выделяется минимальный exploratory budget;
- frozen/killed не получают новый бюджет.

### FR-5 Anti-Thrashing

Система **обязана** ограничивать частоту реприоритизации:

- `min_focus_window_hours` на проект;
- `max_reprioritizations_per_week`;
- `reserved_capacity_for_winners` (например 25%).

### FR-6 Ledger Integration

Каждое решение PFC **обязано** писать событие в ledger:

- `PFC_ADMISSION_DECIDED`
- `PFC_GATE_EVALUATED`
- `PFC_ALLOCATION_UPDATED`
- `PFC_PROJECT_FROZEN`
- `PFC_PROJECT_KILLED`

## 6. Нефункциональные требования

### NFR-1 Надёжность

- Решения PFC детерминированы при одинаковом входе и policy snapshot.
- Повторная обработка событий не должна создавать дубликаты решений (idempotency key).

### NFR-2 Наблюдаемость

- Каждое решение имеет trace-id и policy-version.
- Экспорт метрик в observability стек (Prometheus/OpenTelemetry).

### NFR-3 Производительность

- Admission decision latency p95 < 300 ms (без внешнего web-research).
- Gate batch evaluation (100 проектов) < 5 сек.

## 7. API (v1)

### 7.1 HTTP/gRPC контракты

#### POST `/pfc/admission/evaluate`

Request:

```json
{
  "idea_id": "idea_124",
  "validation_record_id": "vr_124",
  "required_capital": 25000,
  "project_type": "saas_b2b"
}
```

Response:

```json
{
  "decision": "accept",
  "expected_value": 182000,
  "dynamic_cutoff": 75000,
  "reasons": ["ev_above_cutoff", "wip_slot_available"]
}
```

#### POST `/pfc/gate/evaluate`

Request:

```json
{
  "project_id": "project_124",
  "stage": "early_pmf",
  "metrics": {
    "activation_rate": 0.29,
    "retention_d7": 0.23,
    "retention_d30": 0.11
  }
}
```

Response:

```json
{
  "decision": "hold",
  "next_review_at": "2026-03-24T10:00:00Z",
  "reasons": ["retention_d30_below_threshold"]
}
```

#### POST `/pfc/allocation/rebalance`

Response:

```json
{
  "portfolio_budget": 100000,
  "top_tier_share": 0.7,
  "updated_projects": 12,
  "policy_version": "pfc-policy-v1.3"
}
```

## 8. Data model (минимальный)

### Таблица `pfc_policy_snapshots`

- `policy_version` (PK)
- `created_at`
- `wip_limits_json`
- `gate_thresholds_json`
- `allocation_rules_json`

### Таблица `pfc_decisions`

- `decision_id` (PK)
- `decision_type` (`admission|gate|allocation`)
- `entity_id` (`idea_id`/`project_id`)
- `decision` (`accept|reject|pass|hold|freeze|kill|rebalance`)
- `reasons_json`
- `trace_id`
- `policy_version`
- `created_at`

### Таблица `pfc_project_stage_state`

- `project_id` (PK)
- `stage`
- `last_gate_decision`
- `last_gate_at`
- `focus_window_until`
- `reprioritizations_week`

## 9. Метрики успеха (KPI/SLO)

### KPI

- `Scale Conversion Rate` +30% к baseline за 2 квартала;
- `Kill Latency` -40%;
- `Capital Concentration Index` в целевом коридоре 0.6–0.8;
- `Idea-to-Execution Ratio` стабилизация в диапазоне 2:1–4:1.

### SLO

- 99% admission решений < 1 сек;
- 99.9% ledger events записаны без потерь;
- 0 неконсистентных stage transitions.

## 10. Псевдокод ядра решения

```python
def evaluate_admission(idea, validation, portfolio_state, policy):
    ev = expected_value(idea, validation, policy)
    if ev < dynamic_cutoff(portfolio_state, policy):
        return reject("ev_below_cutoff")
    if not has_wip_slot(portfolio_state, policy, stage="incubation"):
        return queue("wip_limit_reached")
    if portfolio_state.treasury < min_runway(validation.project_type, policy):
        return reject("insufficient_treasury")
    return accept(ev)
```

## 11. План внедрения

### Phase 1 — Foundations (1–2 спринта)

- Реализовать policy snapshot + admission endpoint;
- Подключить ledger события admission решений;
- Включить WIP limits в dry-run режиме.

### Phase 2 — Gate & Allocation (2–3 спринта)

- Внедрить Gate Engine;
- Реализовать allocation rebalance джобу;
- Подключить observability dashboard.

### Phase 3 — Enforcement & Optimization (2 спринта)

- Включить hard enforcement;
- Добавить anti-thrashing ограничения;
- Провести A/B на portfolio policy версиях.

## 12. Риски и меры

- **Риск:** слишком агрессивный kill-policy режет потенциальных победителей.  
  **Мера:** hold-режим + human override для top-uncertainty проектов.

- **Риск:** метрики валидации могут быть зашумлены.  
  **Мера:** доверительные интервалы и multi-source evidence score.

- **Риск:** policy drift между командами.  
  **Мера:** versioned policy snapshots + audit trail в ledger.

## 13. Acceptance Criteria

1. Система не создаёт новый проект при достижении WIP-лимита.
2. Каждое admission/gate/allocation решение записывается в ledger с trace-id.
3. Для любого проекта можно восстановить цепочку решений `validation → admission → gate → allocation`.
4. Dashboard показывает минимум 5 ключевых портфельных метрик в near-real-time.
5. Rollout v1 не ухудшает baseline revenue growth (> -5%) в течение пилота.

## 14. Связанные документы

- `docs/AI_VENTURE_ENGINE_IDEA_FLOOD_VS_EXECUTION_BOTTLENECK.md`
- `docs/MODEL_ECONOMY_LAYER.md`
- `docs/MERIT_LEDGER_CONSENSUS.md`
- `docs/OBSERVABILITY_STACK_LS.md`
