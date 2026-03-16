# Техническое задание: внедрение AI-экономики проектов (Creation Ledger + Reward Engine)

## 1) Цель и ожидаемый результат

Внедрить в проект операционный контур, в котором ценность создаётся и измеряется прозрачно:

1. Идеи формируются и проходят фильтрацию.
2. Одобренные инициативы становятся проектами с бюджетом (`treasury`).
3. Проект декомпозируется в задачи, исполняемые агентами и людьми.
4. Каждый значимый вклад фиксируется как `Creation Event` в append-only ledger.
5. Выплаты рассчитываются по подтверждённому эффекту на метрики.
6. Доход проекта частично реинвестируется в новые проекты.

**Итог:** система должна объяснять «почему выплачено именно столько», быть устойчивой к gaming-стратегиям и поддерживать аудит по цепочке «метрика → событие → артефакт → исполнитель».

---

## 2) Scope

### In scope (Phase 1)
- Модель данных: проекты, treasury, задачи, события, выплаты.
- Event API и валидация протокола `Creation Event`.
- Базовый `Reward Engine` (T+7) + отложенные окна (T+30/T+90).
- Базовый `Attribution Engine` по dependency graph.
- Governance-контур споров/override.
- Наблюдаемость, аудит и инварианты целостности.

### Out of scope (Phase 1)
- Юридическая токеномика и on-chain settlement.
- Полностью автономный запуск проектов без human approval.
- Внешний публичный маркетплейс агентов.

---

## 3) Термины

- **Project** — экономическая единица (цель, метрики, roadmap, treasury).
- **Creation Event** — атомарная запись вклада (идея/код/тест/деплой/эксперимент и т.д.).
- **Attribution** — расчёт долей вклада по графу зависимостей.
- **Reward** — начисление за вклад после применения формулы и политик.
- **Policy Version** — версия правил экономики, применяемая к событию/выплате.

---

## 4) Бизнес-требования

1. **Прозрачность:** любое начисление объяснимо и трассируемо.
2. **Справедливость:** учитываются impact, качество, устойчивость, enablement.
3. **Устойчивость:** минимизация стимулов к искусственной активности.
4. **Гибкость:** правила версионируются, поддерживаются миграции политик.
5. **Контроль рисков:** инциденты, rollback, security-fail автоматически влияют на выплаты.

---

## 5) Архитектура (target state)

- **Project Registry** — жизненный цикл проекта и KPI.
- **Task Orchestrator** — декомпозиция roadmap и assignment.
- **Creation Ledger** — append-only события + подписи + idempotency.
- **Attribution Engine** — граф причинности, доли вклада.
- **Reward Engine** — батчи T+7/T+30/T+90, начисления/корректировки.
- **Treasury Service** — доступный баланс, lock, vesting, payout.
- **Policy Engine** — параметры формулы, пороги, правила анти-абьюза.
- **Governance Console** — dispute, override, audit trail.

---

## 6) Функциональные требования

### FR-1. Жизненный цикл проекта
- Статусы: `proposed` → `approved` → `active` → `paused`/`archived`.
- `approved` возможен только при наличии стартового treasury и owner.

### FR-2. Декомпозиция задач
- Каждая задача привязана к этапу roadmap.
- Обязательные поля: `task_id`, `project_id`, `owner`, `reward_budget`, `acceptance_criteria`, `deadline`.

### FR-3. Протокол Creation Event (обязательные поля)
- `event_id`, `project_id`, `timestamp`;
- `actor{type,id,role}`;
- `action{type,task_id,description}`;
- `artifacts[]` (минимум URI + digest/hash);
- `dependencies.parent_event_ids[]`;
- `evaluation.expected_impact{metric,direction,magnitude_estimate}`;
- `quality_signals{tests_passed,review_score,security_status,rollback_within_7d}`;
- `attribution.contributors[]` (доли суммарно 1.0);
- `economics{base_reward,vesting_days}`;
- `governance{policy_version}`.

### FR-4. Валидация события
- Reject, если нет `project_id`/`actor`/`action.type`.
- High-impact action требует верифицируемый artifact.
- Нарушение инвариантов долей атрибуции (`sum != 1.0`) — reject.
- Event с отсутствующим dependency-графом — `low_confidence` (но сохраняется).

### FR-5. Расчёт наград

Формула:

`R = B + α·I + β·P + γ·E − δ·N`

Где:
- `B` — base reward,
- `I` — подтверждённый impact на KPI,
- `P` — persistence эффекта,
- `E` — enablement (ускорение/масштабируемость для других),
- `N` — негативные факторы (rollback/incidents/security).

Выплата:
- 20% мгновенно (provisional),
- 80% после валидации окна,
- при отрицательной корректировке создаётся `negative_adjustment`.

### FR-6. Временные окна
- `T+7` — первичная валидация и основная часть начисления.
- `T+30` — корректировка по устойчивости и качеству.
- `T+90` — финальная стабилизация contribution score.

### FR-7. Anti-gaming
- Нормализация микрособытий (batching/frequency caps).
- Ограничение max reward без подтверждённого эксперимента.
- Auto-penalty для rollback и инцидентов `severity >= medium`.
- Аномалии самоатрибуции и burst-активности отправляются в аудит.

### FR-8. Governance
- Начисления выше порога `governance_threshold` получают dispute window (72ч).
- Override только через `governance_action` с reason + approver.
- Все governance-события immutable и подписаны.

---

## 7) Нефункциональные требования

- Надёжность: idempotency по `event_id`.
- Производительность: `POST /v1/events` p95 < 200ms.
- Batch-производительность: перерасчёт до 1 млн событий < 30 мин.
- Безопасность: подпись события, RBAC/ABAC на операции approve/payout.
- Наблюдаемость: метрики latency/error/disputed-rate/payout-drift.
- Аудит: полный trace payout → events → artifacts → KPI snapshots.

---

## 8) API-контракты (MVP)

### `POST /v1/projects`
Создание проекта.

### `POST /v1/projects/{project_id}/tasks`
Создание задачи.

### `POST /v1/events`
Запись `Creation Event`.

### `POST /v1/rewards/recompute`
Запуск batch-пересчёта (`window=7|30|90`).

### `GET /v1/projects/{project_id}/ledger`
Чтение графа событий проекта.

### `GET /v1/projects/{project_id}/payouts`
История начислений и корректировок.

### `POST /v1/governance/disputes`
Открыть спор по payout.

### `POST /v1/governance/overrides`
Применить override по спору.

---

## 9) SQL DDL (минимум для старта)

```sql
create table projects (
  project_id text primary key,
  name text not null,
  status text not null,
  idea text not null,
  goal text not null,
  success_metrics jsonb not null,
  roadmap jsonb not null,
  created_at timestamptz not null default now()
);

create table project_treasury (
  project_id text primary key references projects(project_id),
  currency text not null,
  available_amount numeric(20,8) not null,
  locked_amount numeric(20,8) not null default 0,
  updated_at timestamptz not null default now()
);

create table creation_events (
  event_id text primary key,
  project_id text not null references projects(project_id),
  timestamp timestamptz not null,
  actor_type text not null,
  actor_id text not null,
  actor_role text not null,
  action_type text not null,
  task_id text,
  payload jsonb not null,
  confidence text not null default 'normal',
  policy_version text not null,
  created_at timestamptz not null default now()
);

create table event_contributors (
  event_id text not null references creation_events(event_id) on delete cascade,
  actor_id text not null,
  share numeric(6,5) not null,
  primary key (event_id, actor_id)
);

create table reward_calculations (
  calc_id bigserial primary key,
  event_id text not null references creation_events(event_id),
  window_days int not null,
  base_reward numeric(20,8) not null,
  impact_score numeric(12,6) not null,
  persistence_score numeric(12,6) not null,
  enablement_score numeric(12,6) not null,
  negative_score numeric(12,6) not null,
  total_reward numeric(20,8) not null,
  status text not null,
  created_at timestamptz not null default now()
);

create table reward_payouts (
  payout_id bigserial primary key,
  calc_id bigint not null references reward_calculations(calc_id),
  project_id text not null references projects(project_id),
  actor_id text not null,
  amount numeric(20,8) not null,
  payout_type text not null,
  status text not null,
  created_at timestamptz not null default now()
);
```

### Инварианты БД
- `creation_events.event_id` уникален (idempotency).
- `sum(event_contributors.share)` по `event_id` должно быть равно `1.0`.
- Нельзя подтвердить payout, если `available_amount < amount`.

---

## 10) State machines

### 10.1 Project state machine
- `proposed` → `approved` (требует treasury > 0)
- `approved` → `active`
- `active` → `paused` | `archived`
- `paused` → `active` | `archived`

### 10.2 Payout state machine
- `draft` → `pending_dispute` (если выше порога)
- `draft` → `ready_to_pay` (если ниже порога)
- `pending_dispute` → `ready_to_pay` | `rejected`
- `ready_to_pay` → `paid`

---

## 11) План внедрения (delivery)

### Phase 1 (2–3 недели)
- Event API + валидация + запись в ledger.
- DDL/миграции таблиц.
- Batch T+7 и provisional payout.
- Базовый dashboard (events/day, payouts/day, disputed-rate).

### Phase 2 (2 недели)
- Dependency graph + attribution scoring.
- Batch T+30/T+90 и корректировки.
- Anti-gaming правила и anomaly flags.

### Phase 3 (1–2 недели)
- Governance disputes/overrides.
- Финальный аудит-трейс и отчёты для finance/product.

---

## 12) Acceptance Criteria (DoD)

1. Повторная отправка `event_id` не создаёт дубль.
2. Любой payout объясним формулой и ссылками на исходные события.
3. Rollback в окне T+30 снижает payout по политике.
4. Спор переводит payout в `pending_dispute` до решения.
5. Ключевые API покрыты контрактными и интеграционными тестами.
6. Есть отчёт по распределению reward и доле disputed payouts.

---

## 13) Тест-план (обязательный минимум)

- Контрактные тесты API (`/projects`, `/events`, `/rewards/recompute`, `/governance/*`).
- Property-based тест: сумма долей атрибуции всегда 1.0.
- Идемпотентность: повтор `POST /v1/events` с одинаковым `event_id`.
- Интеграция: сценарий `code_committed → deploy_done → metric_improved → payout`.
- Негативный сценарий: rollback после payout и корректировка `negative_adjustment`.

---

## 14) RACI (кто отвечает)

- Product/Strategy — KPI, пороги economics, приоритеты проектов.
- Platform/Backend — Ledger API, Reward Engine, миграции.
- Data/ML — impact-сигналы и аномалии anti-gaming.
- Security — подписи, доступы, аудит событий.
- Governance Board — спорные начисления и policy override.

---

## 15) Стартовый справочник типов событий

- `idea_created`
- `hypothesis_validated`
- `spec_written`
- `code_committed`
- `test_added`
- `deploy_done`
- `experiment_run`
- `metric_improved`
- `incident_fixed`
- `refactor_enablement`

---

## 16) Пример жизненного цикла начисления

1. Агент публикует `code_committed` с hash артефакта.
2. После релиза фиксируется `deploy_done`.
3. Эксперимент публикует `metric_improved`.
4. Batch T+7 считает initial impact и создаёт payout (20% уже выплачено).
5. Batch T+30 учитывает rollback/incidents и применяет корректировку.
6. Batch T+90 фиксирует финальный contribution score.

