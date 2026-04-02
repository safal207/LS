# Subconscious → TemporalGraph Feedback Loop + Five-Force Cognitive Field

## Обзор

Система обладает фоновым процессом — **подсознанием** (`_subconscious_loop`), который
непрерывно анализирует историю диалога между ответами и строит гипотезы о когнитивном
режиме пользователя. Эти гипотезы записываются в **TemporalGraph**, где резонанс паттернов
накапливается со временем и начинает влиять на долгосрочное поведение системы.

Дополнительно система поддерживает **пять динамических сил**, которые действуют на каждый
узел графа в каждом цикле `Coordinator.decide()` — создавая живое когнитивное поле, где
узлы конкурируют, забываются, стабилизируются и взаимодействуют друг с другом.

---

## Архитектура петли обратной связи

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AgentLoop                                       │
│                                                                              │
│  ┌──────────────┐   каждые 20с   ┌──────────────────────────┐              │
│  │  Диалог /    │ ─────────────► │  _run_subconscious_pass  │              │
│  │  history     │                │  Анализирует last 12     │              │
│  └──────────────┘                │  сообщений пользователя  │              │
│                                  └────────────┬─────────────┘              │
│                                               │                              │
│  ┌──────────────┐                ┌────────────▼──────────────┐             │
│  │ WorldPoller  │ ─────────────► │       TemporalGraph        │             │
│  │ (git/logs)   │                │                            │             │
│  └──────────────┘                │  nodes["subconscious:*"]   │             │
│                                  │  nodes["lesson:*"]         │             │
│  ┌──────────────┐                │  nodes["world:*"]          │             │
│  │  Quality FB  │                │                            │             │
│  │  (да/нет)    │ ─────────────► │  get_meritocratic_axis()  │             │
│  └──────────────┘                └────────────┬──────────────┘             │
│                                               │                              │
│                          ┌────────────────────▼───────────────────┐        │
│                          │      Coordinator.decide() — 5 Forces    │        │
│                          │                                          │        │
│                          │  F1: apply_orientation_forces()          │        │
│                          │  F2: apply_stabilization_forces()        │        │
│                          │  F3: apply_decay()                       │        │
│                          │  F4: apply_interference()                │        │
│                          │  F5: ← bidirectional signal back         │        │
│                          └────────────────────┬───────────────────┘        │
│                                               │                              │
│                          ┌────────────────────▼───────────────────┐        │
│                          │   _explain_mode_for_item()              │        │
│                          │   "Доминирующий паттерн: deliberative"  │        │
│                          └────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Пять сил когнитивного поля

Каждый вызов `Coordinator.decide()` прогоняет все пять сил через TemporalGraph
в определённом порядке:

### Сила 1: Ориентационные силы (`apply_orientation_forces`)

Переводит внешние сигналы OrientationCenter в резонансные изменения узлов:

| Сигнал | Действие |
|--------|----------|
| `chaos_score` высокий | Ослабляет все узлы пропорционально `chaos * 0.12` |
| `harmony_score` высокий | Усиляет ось (meritocratic axis) на `harmony * 0.10` |
| `drift_pressure` высокий | Усиляет `lesson:*` узлы на `drift * 0.08` |
| `rhythm_phase="inhale"` | Буст `subconscious:reactive` +0.06 |
| `rhythm_phase="exhale"` | Буст `subconscious:deliberative` +0.06 |

Возвращает dict `{node_id: delta}` для observability.

### Сила 2: Стабилизация (`apply_stabilization_forces`)

Mean-reversion к позиции покоя + гистерезис оси:

```
delta = (resting_resonance - current_resonance) * strength * (1 - stability_bias)
```

- Узел выше покоя → тянется вниз
- Узел ниже покоя → тянется вверх  
- Высокий `stability_bias` сопротивляется изменению
- Ось с `stability_bias > 0.5` получает дополнительный consolidation boost (+0.006)

### Сила 3: Кривая забывания (`apply_decay`)

Экспоненциальный распад по типу узла (период полураспада):

| Тип узла | Период полураспада |
|----------|--------------------|
| `lesson:*` | 24 часа |
| `world:git:*` | 1 час |
| `world:error:*` | 30 минут |
| `world:custom:*` | 30 минут |
| `subconscious:*` | 10 минут |
| `world:critical:*` | 5 минут |
| остальные | 5 минут |

Формула: `decay = (r - resting) * (1 - 2^(-dt/half_life)) * (1 - stability_bias * 0.5)`

Узлы со стабильностью забываются медленнее. Резонанс не опускается ниже `resting_resonance`.

### Сила 4: Интерференция (`apply_interference`)

Предотвращает split-brain: конкурирующие режимы гасят друг друга.

Пары интерференции:
```python
("subconscious:reactive", "subconscious:deliberative")
("subconscious:reactive", "subconscious:creative")
```

Более слабый узел в паре теряет `gap * 0.08` резонанса (gap = разница резонансов).
Более сильный остаётся неизменным.

**Эффект:** система не может одновременно быть высокорезонансно reactive И deliberative —
один режим доминирует, другой отступает.

### Сила 5: Обратный сигнал в OrientationCenter

```
trajectory_error_blended = base_error * 0.7 + (1 - axis_resonance) * 0.3
```

Высокий резонанс оси → снижает воспринимаемую ошибку траектории → более стабильная
ориентация в следующем цикле. **Двунаправленный поток.**

---

## Обучение с трёх источников

### 1. Подсознание (unsupervised, каждые 20с)
`_run_subconscious_pass()` анализирует последние 12 сообщений:

| Режим | Условие | Confidence |
|-------|---------|-----------|
| `creative` | brainstorm/invent/design/story... | 0.76 |
| `deliberative` | why/how/explain + 2 длинных реплики | 0.78 |
| `reactive` | всё остальное | 0.66 |

При повторном обнаружении: `resonance += confidence * 0.12`

### 2. Качественная обратная связь (supervised)
Пользователь говорит "да", "отлично", "нет", "плохо" →
`_apply_quality_feedback` изменяет резонанс последнего активного узла:
- Позитив: `+0.18`
- Негатив: `-0.25` (более жёсткий сигнал)

### 3. Рефлексия/уроки (self-directed)
`ingest_reflection(reason, progress)` → `lesson:{slug}` узлы (24ч half-life).
При сне-консолидации (`digest_old_reflections`) — автоматически.

### 4. Внешние события — WorldPoller
Daemon-поток читает git-историю и лог-файлы:
- `world:git:{hash}` — резонанс 0.55–0.75 по размеру коммита
- `world:error:{slug}` — резонанс 0.75
- `world:critical:{slug}` — резонанс 0.90, быстро забывается (5 мин)

---

## Траектория ориентации

`record_orientation_snapshot()` сохраняет до 100 последних состояний OrientationCenter.
`get_orientation_momentum()` вычисляет тренды:

```python
{
    "chaos_trend":      +0.12,   # chaos растёт (плохо)
    "harmony_trend":    -0.05,   # harmony падает
    "axis_stability":    0.87,   # стабильность оси (хорошо)
    "momentum":         -0.23,   # итоговый импульс (chaos↑ > harmony↓)
}
```

Momentum = `harmony_trend * 0.4 - chaos_trend * 0.5 + axis_stability * 0.1`

Это значение поверхностно через `to_orientation_signal()` → `Coordinator.decide()` payload.

---

## Stability Bias — инерция узла

`stability_bias` (0.0–1.0) нарастает когда узел статичен, падает при быстрых изменениях:

```python
def update_resonance(self, new_value):
    velocity = |delta| / dt_s
    if velocity < 0.001:
        stability_bias = min(1.0, bias + 0.08)  # нарастает при покое
    else:
        stability_bias = max(0.0, bias - velocity * 5)  # падает при хаосе
```

Влияет на:
- **Выбор оси**: `stability_score = bias * 0.18` добавляется к meritocratic score
- **Распад**: узел с `bias=0.9` теряет в 1.45× меньше резонанса
- **Стабилизацию**: меньше тянется к resting position
- **Интерференцию**: устойчивые узлы сильнее сопротивляются вытеснению

---

## Конфигурация

| Параметр | Значение | Описание |
|----------|---------|---------|
| `_subconscious_interval_s` | 20.0 | Интервал подсознания (сек) |
| subconscious confidence boost | × 0.12 | Усиление резонанса при повторении |
| resonance threshold for hint | 0.80 | Порог доминирующего паттерна |
| quality feedback positive | +0.18 | Буст за позитивный сигнал |
| quality feedback negative | -0.25 | Штраф за негативный сигнал |
| stabilization strength | 0.06 | Сила mean-reversion |
| decay dt per cycle | 30.0s | Время шага распада |
| orientation forces | per cycle | Силы применяются в каждом decide() |
| trajectory history | 100 | Размер окна снимков ориентации |

---

## Тесты

### `tests/unit/test_stabilization_forces.py` (17 тестов)
- `TestStabilityBias` — нарастание/падение stability_bias, влияние на ось и хаос
- `TestStabilizationForce` — mean-reversion вверх/вниз, consolidation boost для оси
- `TestForgettingCurve` — порядок half-life, decay reduces resonance, stable decays slower
- `TestInterference` — слабый теряет, сильный не меняется, no-op при одном узле
- `TestOrientationTrajectory` — snapshot записывается, momentum+/-, stability_index в сигнале

### `tests/unit/test_orientation_force_ladder.py` (9 тестов)
- chaos ослабляет все узлы
- harmony усиляет ось
- drift_pressure буcтит lesson-узлы
- inhale/exhale буcтят reactive/deliberative
- to_orientation_signal содержит все ключи
- пустой граф → trajectory_signal = 0.5
- высокий резонанс оси снижает trajectory_error
- bidirectional: signal out → forces in → signal out изменился

### `tests/smoke/test_agent_loop.py` (10 тестов)
- subconscious создаёт insight и TemporalNode
- resonance накапливается при повторении
- качественная обратная связь усиляет/ослабляет узлы
- velocity вычисляется и влияет на выбор оси
- reflection lesson может стать осью

---

## Эволюция архитектуры

```
v1: Реактивная система
  Запрос → mode_detector → ответ

v2: Кратковременная память (подсознание)
  Запрос → mode_detector + subconscious_latest → ответ
  (краткосрочный 20с паттерн)

v3: Долговременная ось (TemporalGraph)
  Запрос → mode_detector + subconscious → temporal_axis → ответ
  (resonance накапливается через разговоры)

v4: Самообучение (velocity + feedback + reflection + world)
  4 источника знаний → TemporalGraph
  → velocity_leaders предсказывают будущую ось

v5: Пятисильное когнитивное поле (текущее)
  OrientationCenter ↔ TemporalGraph (двунаправленный поток)
  5 сил создают динамическое равновесие:
    F1: orientation → chaos/harmony изменяют резонанс узлов
    F2: stabilization → mean-reversion + гистерезис оси
    F3: forgetting → экспоненциальный распад по типу узла
    F4: interference → конкурирующие режимы вытесняют друг друга
    F5: axis signal → снижает trajectory_error в OrientationCenter
```

---

## Связанные компоненты

- **`hexagon_core/temporal_graph.py`** — TemporalNode, TemporalGraph, все 5 сил
- **`python/modules/agent/loop.py`** — AgentLoop с subconscious/world потоками и quality feedback
- **`python/modules/agent/world_poller.py`** — WorldPoller: git/logs → TemporalNodes
- **`python/modules/coordinator/coordinator.py`** — Coordinator.decide() запускает все 5 сил
- **`python/modules/llm/temporal.py`** — TemporalContext живёт внутри AgentLoop
- **`python/modules/orientation/center.py`** — OrientationCenter: внешний источник сигналов
