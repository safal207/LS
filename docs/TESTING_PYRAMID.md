# Пирамида Тестирования (Testing Pyramid)

## Overview

Пирамида тестирования — это методология организации тестов по уровням, где каждый уровень имеет определённую цель, scope и количество тестов.

```
                    ┌─────────────┐
                    │   E2E      │  5-10%
                    │   Tests    │  (8 tests)
                    └─────────────┘
               ┌───────────────────┐
               │  Integration     │  15-25%
               │  Tests           │  (pending)
               └───────────────────┘
         ┌───────────────────────────┐
         │      Unit Tests           │  60-80%
         │      (153 tests)          │
         └───────────────────────────┘
```

---

## Уровни Тестирования

### 1. 🟢 Unit Tests (Базовый уровень) — 153 теста

**Цель:** Тестирование отдельных функций, классов и модулей в изоляции.

**Принципы:**
- Каждый тест проверяет одну конкретную функциональность
- Все зависимости замоканы (mocks, stubs, fakes)
- Тесты быстрые (ms - seconds)
- Тесты независимы друг от друга
- 100% воспроизводимость

**Категории Unit Tests:**

#### Codex Module Tests (`tests/unit/`)
```
tests/unit/
├── test_unified_cognitive_loop.py      # UnifiedCognitiveLoop
├── test_workspace_layer.py             # Workspace (GlobalFrame, MeritEngine)
├── test_cooperative_agents.py           # Analyst/Stabilizer/Predictor/Integrator
├── test_narrative_layer.py              # NarrativeGenerator
├── test_self_model_integration.py       # SelfModel, AffectiveLayer
├── test_reflexivity.py                  # FieldReflexivity
├── test_field_*.py                      # Field system (8+ tests)
├── test_coordinator_*.py                 # Coordinator tests (5+ tests)
├── test_lpi_*.py                        # LPI tests (3+ tests)
├── test_causal_memory_layer.py           # CausalMemoryLayer
├── test_model_registry.py                # ModelRegistry
├── test_capu.py                         # CAPU features extraction
└── ... (30+ test files)
```

**Пример Unit Test:**

```python
def test_analyst_agent_processes_frame(self):
    """Test that AnalystAgent extracts correct insights from GlobalFrame."""
    # Arrange
    frame = create_test_global_frame()
    agent = AnalystAgent(name="test-analyst")
    
    # Act
    output = agent.process(frame)
    
    # Assert
    assert output["agent"] == "test-analyst"
    assert "insight" in output
    assert output["confidence"] >= 0.0
```

#### Smoke Tests (`tests/smoke/`) — 19 тестов

**Цель:** Быстрая проверка что ключевые компоненты работают.

```
tests/smoke/
├── test_agent_loop.py            # AgentLoop
├── test_agent_events.py          # Event system
├── test_agent_metrics.py         # Metrics
├── test_agent_task_done.py        # Task completion
├── test_breaker.py                # CircuitBreaker
├── test_config_loader.py          # Config loading
├── test_cotcore_prompt.py         # COT Core
├── test_entrypoint_imports.py      # Imports
├── test_event_contract.py         # Event contracts
├── test_llm_errors.py             # LLM error handling
└── test_temporal.py               # TemporalContext
```

**Характеристики:**
- Время выполнения: < 5 секунд
- Покрытие: критичные пути
- Зависимости: минимум (все мокается)

---

### 2. 🟡 Integration Tests (Средний уровень)

**Цель:** Тестирование взаимодействия между компонентами.

**Текущий статус:** В разработке

**Примеры для реализации:**

```
tests/integration/
├── test_agent_coordination.py      # Agent -> Workspace integration
├── test_memory_persistence.py     # CausalMemory -> Disk
├── test_model_selection.py        # Selector -> Registry -> Loader
└── test_loop_to_narrative.py      # Loop -> Narrative integration
```

**Принципы:**
- Тестируют 2-3 компонента вместе
- Мокаются только внешние зависимости (БД, сеть, файловая система)
- Время выполнения: 1-30 секунд
- Проверяют контракты между модулями

---

### 3. 🔴 E2E Tests (Вершина пирамиды) — 8 тестов

**Цель:** Тестирование полных пользовательских сценариев.

```
tests/e2e/
├── test_agent_loop_cancel.py       # Cancel behavior
├── test_agent_loop_flow.py         # Full flow
├── test_agent_loop_no_cancel.py    # No cancel scenario
├── test_agent_observability.py    # Observability events
├── test_breaker_flow.py           # CircuitBreaker flow
├── test_console_flow.py           # Console entrypoint
├── test_ghostgpt_flow.py          # GUI entrypoint
└── test_temporal_flow.py           # Temporal context flow
```

**Характеристики:**
- Время выполнения: 5-60 секунд
- Минимум моков (только внешние сервисы)
- Покрытие: критичные пользовательские сценарии
- Параллелизация: по возможности

---

## Текущее Покрытие

### По Модулям

| Модуль | Unit | Smoke | E2E | Статус |
|--------|------|-------|-----|--------|
| **Cognitive Loop** | ✅ | ✅ | ✅ | 100% |
| **Workspace** | ✅ | ✅ | - | 90% |
| **Agents** | ✅ | ✅ | ✅ | 100% |
| **Narrative** | ✅ | - | - | 50% |
| **Self-Model** | ✅ | - | - | 70% |
| **Field System** | ✅ | - | - | 60% |
| **Causal Memory** | ✅ | - | - | 50% |
| **Benchmark** | - | ✅ | - | 30% |
| **Registry** | ✅ | - | - | 50% |
| **Circuit Breaker** | - | ✅ | ✅ | 100% |

### Метрики

```
Test Statistics (2025-02-07):
├── Total Tests:     180
├── Unit Tests:      153 (85%)
├── Smoke Tests:     19  (10%)
├── E2E Tests:       8   (5%)
├── Passing:         175 (97%)
└── Known Issues:    5   (mock isolation в полном сьюте)
```

---

## Запуск Тестов

### Быстрый запуск (Smoke + Unit)
```bash
# Только быстрые тесты
python -m pytest tests/unit/ tests/smoke/ -v --tb=short
```

### Полный сьют
```bash
# Все тесты
python -m pytest tests/ -v
```

### По файлу
```bash
# Конкретный тест
python -m pytest tests/unit/test_unified_cognitive_loop.py -v
```

### С покрытием
```bash
# С покрытием кода
python -m pytest tests/unit/ --cov=codex --cov-report=html
```

---

## Best Practices

### 1. Тесты должны быть
- ✅ Изолированными (каждый тест - отдельный сценарий)
- ✅ Детерминированными (одинаковый результат при повторе)
- ✅ Быстрыми (unit < 1s, smoke < 5s, e2e < 60s)
- ✅ Читаемыми (названия говорят о проверке)
- ✅ Независимыми ( порядок не важен)

### 2. Структура теста (AAA Pattern)

```python
def test_something():
    # Arrange - Подготовка
    input_data = create_test_data()
    component = TestComponent()
    
    # Act - Действие
    result = component.process(input_data)
    
    # Assert - Проверка
    assert result.status == "success"
    assert result.data == expected
```

### 3. Именование тестов

```
test_<module>_<method>_<scenario>
├── test_analyst_extracts_insight_from_frame
├── test_selector_returns_best_model
├── test_global_frame_has_all_required_fields
└── test_memory_records_task_success
```

### 4. Mocks и Fixtures

**Использовать:**
- `unittest.mock.Mock` - простые моки
- `unittest.mock.MagicMock` - моки с магическими методами
- `pytest.fixture` - переиспользуемые фикстуры

**Избегать:**
- Моков слишком много (признак - тест не проверяет реальную логику)
- Моков там, где нужна интеграция
- "Моков ради моков"

---

## Roadmap Улучшений

### Текущий Фокус

- [ ] Добавить Integration Tests для критичных путей
- [ ] Увеличить покрытие Narrative до 80%
- [ ] Увеличить покрытие Causal Memory до 80%
- [ ] Добавить property-based тесты для ключевых функций

### Среднесрочные Цели

- [ ] Integration Tests: Agent ↔ Workspace ↔ Memory
- [ ] Performance Tests: Benchmark stability
- [ ] Load Tests: Concurrent agent execution
- [ ] Mutation Testing: Проверка качества тестов

### Долгосрочные Цели

- [ ] 90%+ покрытие критичных модулей
- [ ] Автоматический анализ качества тестов
- [ ] Интеграция с CI/CD
- [ ] Test Impact Analysis

---

## Инструменты

| Инструмент | Назначение |
|------------|------------|
| `pytest` | Основной фреймворк |
| `unittest` | Стандартная библиотека |
| `pytest-cov` | Покрытие кода |
| `pytest-mock` | Фикстуры и моки |
| `unittest.mock` | Mocks и stubs |

---

## Ссылки

- [BUGS.md](./BUGS.md) - Журнал найденных багов
- [BUG_REPORT_TEMPLATE.md](./BUG_REPORT_TEMPLATE.md) - Шаблон репорта
- scripts/bug_tracker.py - Автоматический сканер

---

## Обновлено
2025-02-07
