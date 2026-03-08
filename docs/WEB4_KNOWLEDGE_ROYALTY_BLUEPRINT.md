# Web4 Blueprint: Decentralized Knowledge & Royalty Flows

Этот документ фиксирует **первый чертёж Web4-сети** для обмена идеями между агентами,
оценки полезности и начисления роялти в формате «кредитов опыта».

## 1) Участники сети

| Тип участника | Роль | Что создаёт / получает |
|---|---|---|
| Пользователь | Человек, работающий со своего устройства | Идеи, цели, задачи, контекст и опыт |
| Локальный агент пользователя | Цифровой двойник с памятью и адаптацией | Кодирует идеи в belief/lesson, обучается на outcome |
| Глобальные агенты (supernodes) | Децентрализованные валидаторы и ретрансляторы | Проверяют quality/resonance, распространяют полезные lessons |
| Knowledge Aggregators (Hexagon Core / KACL / TemporalGraph) | Слой агрегации и индексации | Сводят causal/temporal связи, хранят trace применения идей |

## 2) Потоки знаний

### 2.1 Local generation → Agent
1. Пользователь формирует идею/решение.
2. Локальный агент преобразует это в:
   - `belief` (вес, confidence, resonance);
   - `lesson` (контекст применения + outcome);
   - temporal stamp (когда и в каком состоянии возникло знание).

### 2.2 Agent → Web4 network (proof-of-idea)
1. Агент публикует candidate lesson с metadata.
2. Peer-агенты выполняют lightweight validation:
   - similarity/resonance check;
   - полезность по локальной задаче;
   - consistency с causal history.
3. Формируется quality score и решение:
   - `accept`, `defer`, `reject`.

### 2.3 Network → Agent/User (return flow)
1. Сеть возвращает отобранные лучшие lessons.
2. Локальный агент делает controlled merge в LTM:
   - обновляет beliefs;
   - расширяет causal memory;
   - добавляет temporal trace принятия.

### 2.4 Royalty flow (credits-of-experience)
1. При повторном использовании внешней идеи фиксируется факт reuse.
2. Инициатор идеи получает `experience_credit`.
3. Кредиты могут использоваться:
   - для приоритета распространения идей;
   - для доступа к продвинутым ресурсам сети;
   - для будущей внешней monetization-конвертации (за пределами MVP).

## 3) Логическая архитектура

```text
[User]
   |
   v
[Local Agent]
   |  self.memory + causal graph + temporal graph
   v
[Web4 Decentralized Mesh] <---- feedback / lessons ----
   |
   v
[Global Knowledge Aggregators: Hexagon Core / KACL]
   |
   v
[Royalty / Reward Flow] ---> [User / Agent]
```

Ключевые измерители:
- **Causal Graph**: причинные связи между идеями и решениями.
- **Temporal Graph**: эволюция знаний, когда и почему они усилились/ослабли.
- **Resonance/Harmony**: ценность идеи для различных контекстов агентов.

## 4) Принципы сети

1. **Knowledge > Token**: первична практическая полезность идеи.
2. **Adaptive Sharing**: сильные lessons распространяются, шум локализуется.
3. **Self-Governing Agents**: агент сам обновляет bias/политику принятия знаний.
4. **Proof-of-Work Ideas**: ценность подтверждается применением и outcome.
5. **Royalty as Motivation**: вклад в коллективный интеллект вознаграждается кредитом опыта.

## 5) Минимальный протокол (MVP)

### 5.1 Message types
- `LESSON_PROPOSED`
- `LESSON_VALIDATED`
- `LESSON_MERGED`
- `LESSON_REUSED`
- `ROYALTY_CREDITED`

### 5.2 Минимальные поля
- `lesson_id`, `origin_agent_id`, `timestamp`
- `resonance_score`, `quality_score`, `similarity_score`
- `merge_decision`, `decision_reason`
- `reuse_count`, `experience_credit`

## 6) MVP acceptance (первый чертёж)

MVP считается собранным, если:
1. 2 агента обмениваются lessons в демо-сценарии.
2. Есть quality/resonance decision до merge.
3. При reuse внешнего lesson начисляется `experience_credit`.
4. Event-log позволяет восстановить путь: `proposed → validated → merged/rejected → reused → credited`.
