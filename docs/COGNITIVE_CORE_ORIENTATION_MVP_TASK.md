# Техническое задание: развитие центра ориентации и памяти

## 0) Контекст и цель

Цель этапа: собрать **интегрированное когнитивное ядро**, в котором агент непрерывно проходит цикл:

`Input → Reasoning → Action/Output → Outcome → Learning → Memory update`.

На выходе должен быть прототип, готовый к:
- устойчивому локальному обучению на собственных результатах;
- наблюдаемости и реконструкции состояния post-factum;
- базовому обмену знаниями между агентами (Web4-ready).

---

## 1) Область работ (Scope)

### 1.1 In scope
1. Интеграция памяти (Rust + Python fallback) в единый runtime path.
2. Подключение feedback loops в `AgentLoop`/`Coordinator`/`Amygdala`.
3. Реализация центра ориентации (единый snapshot + rollback/restore).
4. Прототип peer-to-peer обмена уроками/рефлексиями между агентами.
5. Dashboard + observability контракт для восстановления когнитивного состояния.
6. MVP-цепочка end-to-end с тестовым сценарием.

### 1.2 Out of scope (на этот этап)
- Полноценная токеномика/криптоэкономика.
- Production-grade consensus между >2 агентами.
- Полноценный distributed storage слой.

---

## 2) Приоритеты и фазы

- **P0 (критично, сначала):** Блоки 1, 2, 3.
- **P1 (после стабилизации P0):** Блок 5.
- **P2 (экспериментально):** Блок 4.
- **Release gate:** Блок 6 как финальная сборка MVP.

Рекомендуемый порядок: `1 → 2 → 3 → 5 → 4 → 6`.

---

## 3) Детализация задач

## 3.1 Интеграция ядра (P0)

### Задачи
1. Проверить единый интерфейс памяти:
   - Rust backend: `RustCausalMemory`;
   - fallback: Python memory backend.
2. Убедиться, что `AgentLoop` в основном ходе использует:
   - `self.memory` для контекста и recall;
   - causal/temporal слой для причинно-временных связей.
3. Привести события к общему event-contract:
   - изменения state;
   - изменения memory;
   - изменения beliefs.

### Definition of Done
- Есть runtime-проверка/лог маркер, какой backend памяти активен.
- Нет «молчаливых» bypass-path, где память обновляется вне общего API.
- Все ключевые когнитивные мутации публикуются в EventBus.

### Артефакты
- Unified memory adapter (Python слой).
- Contract tests на Rust/Python parity.
- Документация data-flow input→memory→output.

---

## 3.2 Feedback loops и обучение (P0)

### Задачи
1. Подключить `amygdala.learn_from_outcome()` к post-action этапу `AgentLoop`.
2. Обновлять через loop:
   - `adaptive_bias`;
   - `personality_p`;
   - `visceral_state`;
   - snapshot эмоционально-когнитивного баланса.
3. В `Coordinator`:
   - фиксировать результат через `record_outcome()`;
   - пересчитывать `compute_trajectory_error()`.
4. В Reflection/Metabolism:
   - `digest_old_reflections()` порождает новые beliefs c весом/resonance.

### Definition of Done
- После серии интеракций видно изменение хотя бы 2 адаптивных параметров.
- Ошибка траектории (`trajectory_error`) обновляется детерминированно по outcome.
- Новые beliefs после digestion появляются в общем belief-store и доступны в snapshot.

### Артефакты
- Интеграционные тесты feedback-loop.
- Метрики до/после (error_rate, confidence drift, resonance changes).

---

## 3.3 Центр ориентации (P0)

### Задачи
1. Консолидировать единое состояние центра ориентации:
   - beliefs;
   - causal edges;
   - temporal nodes;
   - mission state;
   - CoT trace metadata (без утечки приватного chain-of-thought контента).
2. Реализовать API:
   - `get_cognitive_snapshot()`;
   - `restore_cognitive_snapshot(snapshot_id|payload)`;
   - `diff_cognitive_snapshots(a, b)`.
3. Добавить hooks для `AgentLoop` и `Coordinator`.

### Definition of Done
- Snapshot можно сериализовать/восстановить без потери критичных связей.
- Доступен сценарий “альтернативная симуляция”: rollback → replay → сравнение.
- `AgentLoop` и `Coordinator` используют центр ориентации как source of truth.

### Артефакты
- Модуль `orientation_center` (или эквивалент в текущей структуре).
- API contract + schema snapshot payload.
- Тест rollback/restore.

---

## 3.4 Подготовка к децентрализованному обучению (Web4) (P2)

### Задачи
1. Зафиксировать dual-protocol модель: Human-Agent (H→A/A→H) и Agent-Agent (A→A) с event-level контрактом.
2. Прототип обмена знаниями между 2 агентами:
   - best lessons;
   - selected reflections.
3. Добавить легковесную валидацию идеи:
   - quality score / challenge (PoW-light или quality proof);
   - без токенов, по полезности и согласованности.
4. Перед merge в локальную память:
   - resonance/similarity scoring;
   - policy `accept / defer / reject`.

### Definition of Done
- Демо: агент A передает lesson, агент B оценивает и решает включение.
- Решение о merge логируется с объяснимым score breakdown.

### Артефакты
- Minimal protocol message для lesson exchange.
- Merge-policy модуль для внешних lessons.
- Blueprint Web4 knowledge/royalty flows: `docs/WEB4_KNOWLEDGE_ROYALTY_BLUEPRINT.md`.

---

## 3.5 Мониторинг и визуализация (P1)

### Задачи
1. Добавить dashboard-срезы:
   - beliefs count/weight distribution;
   - causal edges;
   - temporal nodes;
   - confidence;
   - memory usage.
2. Подключить observability sink с event-contract для реконструкции состояния.
3. Сделать timeline-view изменения cognitive kernel параметров.

### Definition of Done
- По event log можно восстановить когнитивное состояние в заданный момент времени.
- Dashboard отражает динамику параметров минимум за N последних интеракций.

### Артефакты
- Event schema для `cognitive_state_updated` / `lesson_merged` / `snapshot_restored`.
- UI/CLI виджеты мониторинга.

---

## 3.6 MVP сборка (Release gate)

### Сквозной поток
`Input → AgentLoop → Coordinator → Amygdala → Memory/TemporalGraph → Output`

### Обязательные возможности MVP
1. Feedback loops и обновление lessons в LTM.
2. Snapshot центра ориентации (save + restore).
3. Базовый observability контур + dashboard минимум в read-only режиме.

### Acceptance Criteria
- Проход интеграционного сценария end-to-end без ручных патчей.
- Наличие трассировки, подтверждающей цикл “действие → outcome → learning”.
- Документированная процедура воспроизведения демо.

---

## 4) Архитектурные constraints

1. Event-first: когнитивные изменения должны быть наблюдаемы через шину событий.
2. Deterministic replay: ключевые шаги должны поддерживать воспроизводимость.
3. Memory backend neutrality: одинаковое поведение при Rust/Python backend.
4. Safety by design: внешние lessons не попадают в ядро без policy-валидации.
5. Chain-of-thought hygiene: в snapshot/telemetry хранится только безопасная metadata.

---

## 5) План тестирования

1. **Unit tests**:
   - memory adapter parity;
   - scoring/merge policy;
   - snapshot serialization.
2. **Integration tests**:
   - AgentLoop↔Coordinator↔Amygdala feedback;
   - restore/rollback simulation.
3. **Scenario test (MVP)**:
   - 10+ интеракций с фиксацией trajectory error и изменений beliefs.
4. **Observability test**:
   - reconstruction cognitive state из event-log.

---

## 6) Риски и mitigation

- **Риск:** расхождение поведения Rust и Python памяти.
  - **Mitigation:** contract tests + golden traces.
- **Риск:** деградация производительности из-за избыточных snapshot.
  - **Mitigation:** инкрементальные snapshot/delta storage.
- **Риск:** шумные/вредные lessons из внешних агентов.
  - **Mitigation:** threshold, quarantine queue, delayed merge.

---

## 7) Ожидаемый результат за 1 месяц

Рабочий прототип когнитивного ядра, где:
- агент учится на outcome;
- причинно-временная память интегрирована в основной цикл;
- доступен центр ориентации с snapshot/restore;
- есть базовая наблюдаемость и понятная диагностика;
- подготовлен фундамент для децентрализованного обмена знаниями.
