# -*- coding: utf-8 -*-
# Subconscious → TemporalGraph Feedback Loop

## Обзор

Система обладает фоновым процессом — **подсознанием** (`_subconscious_loop`), который
непрерывно анализирует историю диалога между ответами и строит гипотезы о когнитивном
режиме пользователя. Начиная с коммита `32adf97`, эти гипотезы записываются в
**TemporalGraph**, где резонанс паттернов накапливается со временем и начинает влиять
на долгосрочное поведение системы.

---

## Архитектура петли обратной связи

```
┌─────────────────────────────────────────────────────────────────┐
│                        AgentLoop                                │
│                                                                  │
│  ┌──────────────┐   каждые 20с   ┌──────────────────────────┐  │
│  │  Диалог /    │ ─────────────► │  _run_subconscious_pass  │  │
│  │  history     │                │                          │  │
│  └──────────────┘                │  Анализирует last 12     │  │
│                                  │  сообщений пользователя  │  │
│                                  │                          │  │
│                                  │  → creative (0.76)       │  │
│                                  │  → deliberative (0.78)   │  │
│                                  │  → reactive (0.66)       │  │
│                                  └────────────┬─────────────┘  │
│                                               │                 │
│                          ┌────────────────────▼──────────┐     │
│                          │  memory["subconscious_latest"] │     │
│                          │  memory["subconscious_insights"]│     │
│                          └────────────────────┬──────────┘     │
│                                               │                 │
│                          ┌────────────────────▼──────────┐     │
│                          │         TemporalGraph          │     │
│                          │                               │     │
│                          │  nodes["subconscious:mode"]   │     │
│                          │    resonance += conf * 0.12   │     │
│                          │    (каждый повторный проход)  │     │
│                          └────────────────────┬──────────┘     │
│                                               │                 │
│                          ┌────────────────────▼──────────┐     │
│                          │    get_meritocratic_axis()     │     │
│                          │                               │     │
│                          │  Возвращает узел с макс.      │     │
│                          │  resonance * (1+harmony)      │     │
│                          └────────────────────┬──────────┘     │
│                                               │                 │
│                          ┌────────────────────▼──────────┐     │
│                          │   _explain_mode_for_item()     │     │
│                          │                               │     │
│                          │  Если resonance >= 0.80:      │     │
│                          │  "Доминирующий паттерн:       │     │
│                          │   deliberative (резонанс 0.92)"│     │
│                          └───────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Компоненты

### 1. `_subconscious_loop` — фоновый поток
**Файл:** `python/modules/agent/loop.py`

Запускается при старте `AgentLoop.start()` как daemon-поток с именем `"subconscious"`.
Выполняет `_run_subconscious_pass()` каждые **20 секунд** (настраивается через
`_subconscious_interval_s`). Корректно завершается при `stop()` через
`_subconscious_stop` Event.

### 2. `_run_subconscious_pass` — анализ паттерна
Берёт последние **12 сообщений** из `history`, извлекает реплики пользователя и
классифицирует паттерн:

| Режим | Условие | Confidence |
|-------|---------|-----------|
| `creative` | cues: brainstorm, invent, design, story, ideya... | 0.76 |
| `deliberative` | cues: why, how, explain, reason / 2+ длинных реплики | 0.78 |
| `reactive` | всё остальное | 0.66 |

**После классификации:**
1. Сохраняет insight в `memory["subconscious_latest"]` и `memory["subconscious_insights"][-20:]`
2. Записывает/усиляет `TemporalNode` в `self.temporal.nodes`

### 3. TemporalNode для когнитивного режима

```python
TemporalNode(
    id=f"subconscious:{suggested_mode}",   # e.g. "subconscious:deliberative"
    resonance=confidence,                   # начальный (0.66–0.78)
    harmony_bonus=len(route) * 0.05,       # +0.05 за каждый движок в маршруте
)
```

**При повторном обнаружении того же режима:**
```python
existing.resonance = min(1.0, existing.resonance + confidence * 0.12)
```

Пример роста при трёх deliberative-проходах:
```
Pass 1:  0.780  (начальный)
Pass 2:  0.874  (+0.094)
Pass 3:  0.967  (+0.094)  ← пересекает порог 0.80
```

### 4. `_explain_mode_for_item` — двухуровневый контекст

Функция теперь собирает **два слоя** контекста:

**Краткосрочный** (subconscious_latest, порог confidence ≥ 0.72):
```
Фон: User trend: repeatedly asks for causal explanation and depth.
```

**Долгосрочный** (TemporalGraph axis, порог resonance ≥ 0.80):
```
Доминирующий паттерн: deliberative (резонанс 0.97).
```

Итоговое объяснение режима:
```
Режим deliberative: глубокий анализ. Маршрут: reasoning_engine, verifier.
Доминирующий паттерн: deliberative (резонанс 0.97). Фон: User trend: ...
```

---

## Жизненный цикл резонанса

```
Новый разговор
    ↓
Нет узлов в TemporalGraph
    ↓
Подсознание работает 20с, нет достаточной истории → pass
    ↓
4+ сообщений накоплено → первая классификация
    ↓
Создаётся TemporalNode (resonance ~0.7)
    ↓
Паттерн повторяется → resonance накапливается
    ↓
resonance >= 0.80 → узел становится осью (meritocratic axis)
    ↓
Ось влияет на объяснение каждого ответа
    ↓
prune_weak_nodes(threshold=0.25) не удаляет его (resonance >> 0.25)
    ↓
Доминирование сохраняется до смены паттерна
```

---

## Смена паттерна

Если пользователь резко меняет стиль (переходит с `deliberative` на `creative`),
начинает накапливаться **новый узел** `subconscious:creative`, пока старый
`subconscious:deliberative` постепенно не подвергнется `prune_weak_nodes` или пока
новый не выйдет на более высокий резонанс и не займёт ось.

Нет принудительного сброса — смена происходит органично через конкуренцию резонансов.

---

## Конфигурация

| Параметр | Значение по умолчанию | Описание |
|----------|-----------------------|---------|
| `_subconscious_interval_s` | `20.0` | Интервал между проходами (сек) |
| min history len | `4` | Минимум сообщений для анализа |
| max history window | `12` | Кол-во последних сообщений для анализа |
| long turn threshold | `10 слов` | Порог "длинной" реплики |
| confidence boost per pass | `* 0.12` | Усиление резонанса при повторении |
| resonance threshold for hint | `0.80` | Порог вывода доминирующего паттерна |
| subconscious confidence threshold | `0.72` | Порог для Фон-подсказки |
| max stored insights | `20` | Размер окна `subconscious_insights` |

---

## Тесты

`tests/smoke/test_agent_loop.py`:

| Тест | Что проверяет |
|------|--------------|
| `test_subconscious_pass_creates_latest_insight` | insight создаётся в memory |
| `test_subconscious_feeds_temporal_graph` | TemporalNode создаётся в temporal.nodes |
| `test_subconscious_resonance_accumulates` | повторный проход усиляет резонанс |
| `test_temporal_axis_drives_explanation_hint` | axis с resonance≥0.80 попадает в объяснение |

---

## Связанные компоненты

- **`hexagon_core/temporal_graph.py`** — `TemporalNode`, `TemporalGraph`, `get_meritocratic_axis`, `align_to_axis`
- **`python/modules/llm/temporal.py`** — `TemporalContext(TemporalGraph)` — живёт внутри AgentLoop
- **`python/modules/coordinator/coordinator.py`** — Coordinator v0.2 читает `subconscious_latest` для pre-routing
- **`python/modules/coordinator/mode_detector.py`** — синхронный анализ текущего вопроса (краткосрочный)
- **`codex/causal_memory/amygdala.py`** — эмоциональный фон, влияет на `_blocked_response_text`

---

## Эволюция архитектуры

```
До (реактивная система):
  Запрос → mode_detector → ответ

После (проактивная система):
  Запрос → mode_detector + subconscious_latest + temporal_axis → ответ
             ↑                        ↑                 ↑
             синхронно            краткосрочно     долгосрочно
             (текущий вопрос)     (20с окно)       (весь разговор)
```

Это третий слой непрерывного состояния системы наряду с:
1. **EndocrineSystem** — эмоциональный гормональный фон
2. **TemporalGraph (causal)** — причинно-следственная память событий
3. **Subconscious → TemporalGraph** — когнитивный характер разговора *(новое)*
