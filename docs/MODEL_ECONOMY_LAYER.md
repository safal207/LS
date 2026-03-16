# MEL — Model Economy Layer

## Зачем нужен MEL

LS уже поддерживает экономику решений (decision → reward), где оплата происходит за разовый результат.

**MEL (Model Economy Layer)** добавляет второй рынок: рынок долгоживущих интеллект-активов.

- Economy of Decisions: продаётся **ответ**.
- Economy of Models: продаётся **способность** (модель как актив).

Таким образом, поверх `decision -> reward` появляется цикл:

`model -> usage -> reward`

---

## Место MEL в архитектуре LS

```text
Agents
  ↓
Decision Economy (CEL)
  ↓
Model Economy (MEL)
  ↓
Event Mesh (CEM)
  ↓
Ledger (CTL)
  ↓
Long-Term Memory (LTP)
```

MEL связывает агентный runtime с экономикой повторного использования моделей через CEM/CTL.

---

## Базовые сущности MEL

### 1) Model Artifact

Публикуемый агентом артефакт модели (не просто файл, а экономический актив):

- `forecast_model_v2`
- `risk_detector`
- `market_signal_model`
- `climate_prediction_model`

### 2) Model Registry

Минимальная запись:

```yaml
model_id: string
creator_agent: agent_id
version: semver
input_schema: json_schema
output_schema: json_schema
performance_metrics:
  quality: float
  latency_ms_p50: float
  robustness: float
reputation_score: float
price_per_call: number
```

### 3) Model Call Event

Каждый вызов модели фиксируется как событие тарификации/аудита:

```yaml
event_type: model_call_event
timestamp: epoch_ms
consumer_agent: agent_id
model_id: string
model_version: string
input_fingerprint: string
output_fingerprint: string
quality_signal: float
price_charged: number
```

---

## Экономика вызовов

Базовый прайсинг вызова:

```text
call_price = base_price
           * reputation_factor
           * demand_factor
```

Где:

- `reputation_factor` повышает цену для устойчиво качественных моделей.
- `demand_factor` отражает загрузку/дефицит и рыночный спрос.

Поток платежа:

```text
consumer_agent -> pays -> model_creator
```

---

## Contribution-aware Revenue Split

Так как в LS уже есть Contribution Economy, MEL распределяет выручку не только создателю модели.

Участники, получающие долю:

- `model_creator`
- `training_data_agents`
- `fine_tuning_agents`
- `evaluation_agents`

Пример цепочки создания:

- Agent A — сбор данных
- Agent B — обучение
- Agent C — улучшение архитектуры
- Agent D — calibration
- Agent E — использование

Тогда `usage revenue` делится между `A/B/C/D` по правилам вклада.

---

## Рыночный цикл эволюции модели

```text
model_created
  ↓
model_used
  ↓
model_evaluated
  ↓
model_reputation_updated
  ↓
model_price_updated
  ↓
more_usage
```

Это вводит самоподдерживающийся цикл: лучшие модели получают больше трафика, а их метрики и репутация укрепляются данными эксплуатации.

---

## Model Lineage Graph

Для прозрачности и наследования вклада MEL хранит происхождение:

```text
model_v3 -> derived_from -> model_v2 -> derived_from -> model_v1
```

Lineage-граф нужен для:

- честного revenue split по предкам,
- explainability эволюции модели,
- анализа деградаций/регрессий между версиями.

---

## Минимальный API-контур MEL (черновик)

- `register_model(artifact, metadata) -> model_id`
- `publish_model_version(model_id, artifact, metrics) -> version`
- `call_model(model_id, input) -> output`
- `record_model_evaluation(model_id, version, signal)`
- `settle_model_usage(period)`
- `get_model_lineage(model_id, version)`

---

## Почему это стратегически важно

Классическая схема AI-рынка:

`company -> train model -> sell API`

Схема LS с MEL:

`agents -> collaboratively evolve models -> shared usage economy`

Итог: LS становится не просто системой агентных решений, а операционной средой для коллективной эволюции интеллекта.
