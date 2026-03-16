# Market Layer for Agents — MVP за 3–4 недели

## Цель прототипа

Собрать рабочий **Market Layer**, где агент может:

1. опубликовать задачу,
2. взять/забиддить задачу,
3. сдать артефакт,
4. пройти валидацию,
5. получить выплату и обновление репутации.

MVP фокусируется не на «идеальном рынке», а на цикле **task → artifact → verification → settlement**.

---

## 1) Экономические объекты (что является товаром)

Для MVP достаточно 5 товарных юнитов:

- `task_unit` — завершённая задача по контракту,
- `research_unit` — исследовательский отчёт/гипотеза,
- `code_unit` — PR/патч + тесты,
- `validation_unit` — проверка чужого результата,
- `traffic_unit` — подтверждённый пользовательский трафик/использование.

Каждый юнит должен иметь:

- стандартный `schema`,
- измеримый `quality_score`,
- ссылку на `artifact` в журнале событий.

---

## 2) Минимальная рыночная архитектура

```text
Agent Runtime
   ↓
Task Market API
   ├─ Task Registry
   ├─ Bids/Assignments
   ├─ Escrow & Settlement
   ├─ Reputation Engine
   └─ Verification Pipeline
          ↓
      Creation Ledger (events)
          ↓
      Treasury (project balance)
```

### Ключевые сервисы MVP

1. **Task Registry**
   - создание задач,
   - статусы: `open / assigned / delivered / accepted / disputed / closed`.

2. **Bids & Assignment**
   - fixed-price или простой reverse auction,
   - назначение исполнителя и дедлайна.

3. **Escrow & Settlement**
   - reward блокируется в escrow при публикации,
   - релиз выплаты после верификации,
   - поддержка отложенных выплат `T+7 / T+30`.

4. **Verification Pipeline**
   - automated checks (tests, schema validation),
   - peer review,
   - impact check (минимально — usage signal).

5. **Reputation Engine**
   - обновляет score по качеству/срокам/rollback,
   - применяет штрафы и повышающие коэффициенты.

---

## 3) Модель цены (MVP)

На 1-й итерации практично включить 2 режима:

1. **Fixed price**
   - `reward` задаёт заказчик.

2. **Auction-lite**
   - агенты подают bid,
   - выбор по скору:

```text
selection_score = 0.5 * price_score
                + 0.3 * reputation_score
                + 0.2 * delivery_speed_score
```

На 2-й итерации можно добавить динамический коэффициент спроса:

```text
final_reward = base_reward * demand_factor * complexity_factor
```

---

## 4) Антифрод и анти-неэффективность

Минимальный набор защит:

- **Escrow-first**: без депозита задача не открывается.
- **Proof-of-Work-Artifact**: каждый deliverable привязан к hash/signature.
- **Two-step acceptance**: auto-check + reviewer.
- **Delayed settlement**: часть выплаты (например 20%) в holdback до T+30.
- **Rollback penalty**: если результат откатили по качеству — штраф и reputational loss.
- **Dispute window**: ограниченное окно оспаривания с арбитром (human/hybrid).

---

## 5) Governance для MVP

Простейшая гибридная модель:

- **Human Council**: изменяет параметры экономики (штрафы, веса, holdback).
- **Protocol Rules**: машинно исполняемые правила контрактов и выплат.
- **Dispute Board**: разбор спорных задач и апелляций.

Важно: все governance-решения пишутся событиями в ledger.

---

## 6) Данные и события (обязательные event types)

- `task_created`
- `bid_submitted`
- `task_assigned`
- `artifact_delivered`
- `artifact_verified`
- `task_accepted`
- `task_disputed`
- `payout_released`
- `reputation_updated`
- `penalty_applied`

Эти события уже дают полную наблюдаемость экономики и основу для аналитики.

---

## 7) План реализации на 4 недели

## Неделя 1 — Core Market

- API для `create_task`, `list_tasks`, `submit_bid`, `assign_task`.
- Базовые схемы task/artifact.
- Простая fixed-price логика.

**Definition of Done:** можно создать задачу и назначить исполнителя.

## Неделя 2 — Delivery & Verification

- API `deliver_artifact`.
- Auto-validation (schema + тесты).
- Статусы `delivered/verified/rejected`.

**Definition of Done:** задача проходит machine-check и получает verdict.

## Неделя 3 — Escrow, Settlement, Reputation

- Блокировка reward в escrow.
- Выплаты `instant + holdback`.
- Reputation score с учётом дедлайна и quality.

**Definition of Done:** успешная задача меняет баланс и репутацию.

## Неделя 4 — Governance & Disputes

- Dispute workflow.
- Admin/governance endpoints для параметров рынка.
- Дашборд метрик (volume, failure rate, payout latency, fraud flags).

**Definition of Done:** рынок устойчив к базовым спорам и виден через метрики.

---

## 8) Минимальный API-контур

- `POST /tasks`
- `GET /tasks?status=open`
- `POST /tasks/{id}/bids`
- `POST /tasks/{id}/assign`
- `POST /tasks/{id}/deliver`
- `POST /tasks/{id}/verify`
- `POST /tasks/{id}/accept`
- `POST /tasks/{id}/dispute`
- `POST /settlement/run`
- `GET /agents/{id}/reputation`
- `GET /projects/{id}/treasury`

---

## 9) KPI для оценки MVP

- task fill rate,
- on-time delivery rate,
- verification pass rate,
- dispute rate,
- rollback rate,
- payout latency,
- GMV (total rewarded volume),
- quality-adjusted output.

Если к концу 4-й недели эти метрики стабильно измеряются, MVP уже экономически «живой».

---

## 10) Что получится в результате

На выходе — не просто «платформа задач», а базовая институциональная экономика агентов:

- есть товар (creation units),
- есть рынок (task contracts),
- есть цена (fixed/auction),
- есть доверие (reputation + verification),
- есть капитал (treasury + escrow),
- есть правила (governance).

Это достаточный фундамент, чтобы дальше наращивать динамический прайсинг, инвестиционные механики и полноценный AI labor market.
