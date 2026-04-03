# -*- coding: utf-8 -*-
# Cognitive Field — полная архитектура когнитивного поля

## Обзор

Когнитивное поле системы — живая, самонастраивающаяся сеть узлов (TemporalGraph),
на которую действуют **7 сил** и **6 обучающих механизмов**. Система не просто
отвечает на вопросы — она развивает когнитивный характер и помнит свои паттерны.

---

## Архитектура: полная схема

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          COGNITIVE FIELD                                     ║
║                                                                              ║
║   ┌─────────────┐   каждые 20с  ┌────────────────────────────────────────┐ ║
║   │  Диалог     │──────────────►│         _subconscious_loop             │ ║
║   │  история    │               │  Анализ 12 сообщений → режим+confidence│ ║
║   └─────────────┘               └───────────────────┬────────────────────┘ ║
║                                                      │                       ║
║   ┌─────────────┐               ┌───────────────────▼────────────────────┐ ║
║   │ WorldPoller │──────────────►│           TemporalGraph                │ ║
║   │ git/logs    │               │                                        │ ║
║   └─────────────┘               │  Узлы:   subconscious:*               │ ║
║                                 │          lesson:*    world:*           │ ║
║   ┌─────────────┐               │          lesson:meta:*                │ ║
║   │ Quality FB  │──────────────►│          lesson:session:*             │ ║
║   │ да/нет      │               │                                        │ ║
║   └─────────────┘               │  Рёбра:  link_nodes() → links{}       │ ║
║                                 └───────────────────┬────────────────────┘ ║
║   ┌─────────────┐                                   │                       ║
║   │ Auto Proxy  │───────────────────────────────────┘                       ║
║   │ длина ответа│                                                            ║
║   └─────────────┘                                                            ║
║                                                      │                       ║
║              ┌───────────────────────────────────────▼──────────────────┐  ║
║              │              Coordinator.decide() — 7 сил                 │  ║
║              │                                                            │  ║
║              │  F1+F2: apply_orientation_forces() ← chaos/harmony/drift  │  ║
║              │         + associative propagation + co-activation         │  ║
║              │  F3:    apply_stabilization_forces() ← mean-reversion     │  ║
║              │  F4:    apply_decay()               ← forgetting curve    │  ║
║              │  F5:    apply_interference()        ← split-brain guard   │  ║
║              │  F6:    observer.observe_and_correct() ← adequacy guardian│  ║
║              │  F7:    apply_association_boost()   ← linked nodes boost  │  ║
║              └───────────────────────────────────────┬──────────────────┘  ║
║                                                       │                      ║
║              ┌────────────────────────────────────────▼──────────────────┐ ║
║              │     to_orientation_signal() → OrientationCenter           │ ║
║              │                                                            │ ║
║              │  trajectory_signal, stability_index, momentum             │ ║
║              │  predicted_axis_id, predicted_axis_resonance              │ ║
║              │  adequacy.score, adequacy.pathologies                     │ ║
║              └────────────────────────────────────────────────────────────┘ ║
║                                                                              ║
║  При sleep: observer.session_report() → lesson:session:* → TemporalGraph   ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Семь сил (Forces)

| # | Метод | Что делает |
|---|-------|-----------|
| F1+F2 | `apply_orientation_forces()` | chaos/harmony/drift/rhythm изменяют резонансы + auto-propagation по рёбрам |
| F3 | `apply_stabilization_forces()` | Mean-reversion к resting_resonance + гистерезис оси |
| F4 | `apply_decay()` | Экспоненциальный распад по half-life типа узла |
| F5 | `apply_interference()` | Конкурирующие режимы подавляют друг друга |
| F6 | `observer.observe_and_correct()` | Мета-наблюдатель: корректирует патологии поля |
| F7 | `apply_association_boost()` | Активные узлы усиливают связанных соседей |

**Порядок выполнения в каждом `Coordinator.decide()`:** F1+F2 → F3 → F4 → F5 → F7 → F6

---

## Шесть обучающих механизмов

### 1. Подсознание (каждые 20с, unsupervised)
`_subconscious_loop` → `_run_subconscious_pass` анализирует последние 12 сообщений

| Режим | Условие | Confidence |
|-------|---------|-----------|
| `creative` | brainstorm/invent/design... | 0.76 |
| `deliberative` | why/how/explain + длинные реплики | 0.78 |
| `reactive` | всё остальное | 0.66 |

При повторении: `resonance += confidence × 0.12`

### 2. Качественная обратная связь (supervised)
- Явная: пользователь говорит "да/отлично" → `+0.18`, "нет/плохо" → `−0.25`
- Прокси (Feature 5): длинный ответ + короткая реакция → `−0.10 (авто)`; короткий ответ + развёрнутая реакция → `+0.08 (авто)`

### 3. Рефлексия/уроки (self-directed)
`ingest_reflection()` → `lesson:{slug}` узлы (half-life 24h).
Автоматически при sleep consolidation из `digest_old_reflections()`.

### 4. Внешние события — WorldPoller
| Тип | node_id | Resonance | Half-life |
|-----|---------|-----------|-----------|
| git commit | `world:git:{hash}` | 0.55–0.75 | 1 час |
| error log | `world:error:{slug}` | 0.75 | 30 мин |
| critical | `world:critical:{slug}` | 0.90 | 5 мин |

### 5. Ассоциативный граф (Feature 1, Codex)
`link_nodes(a, b, weight)` — создаёт рёбра между узлами.
- **Co-activation**: когда два узла активируются одновременно → их связь автоматически усиливается (`_reinforce_coactivation_unlocked`)
- **Propagation**: при `add_or_update` изменение распространяется по рёбрам (`_propagate_associative_boost_unlocked`)
- **Explicit boost** (F7): `apply_association_boost(threshold=0.72)` — явный pass в каждом цикле

### 6. Мета-уроки и сессионный отчёт (Feature 2 + 6)
- **Мета-уроки**: если патология появляется ≥ 3 раз → `lesson:meta:{pathology}_pattern` (observer учится собственным слабостям)
- **Ночной отчёт**: при sleep → `observer.session_report()` → `lesson:session:{pathology}` + оценка качества сессии

---

## Причинный граф (Edges)

```python
# Создать связь
graph.link_nodes("subconscious:creative", "lesson:brainstorm", weight=0.25)

# Усилить существующую
graph.link_nodes("a", "b", weight=0.35)  # max(current, new)

# Получить связанных соседей
graph.get_linked_nodes("subconscious:creative")
# → [("lesson:brainstorm", 0.25), ...]

# Явный associative boost (F7)
deltas = graph.apply_association_boost(threshold=0.72, boost_factor=0.07)
```

При `prune_weak_nodes` — все рёбра к удалённому узлу очищаются.

---

## Предиктивная ось (Feature 3)

```python
# Кто будет осью через 60 секунд?
pred = graph.predictive_axis(horizon_s=60.0)
# → TemporalNode с max((resonance + velocity×60) × (1+harmony))

# В каждом сигнале:
signal = graph.to_orientation_signal()
signal["predicted_axis_id"]        # → "subconscious:deliberative"
signal["predicted_axis_resonance"] # → 0.72 (текущий, не предсказанный)
```

Позволяет Coordinator заранее готовить ресурсы под следующую ось.

---

## Профиль пользователя (Feature 4)

```python
store = UserProfileStore()
store.record_turn("user_42", "deliberative")  # после каждого ответа

hint = store.get_starting_hint("user_42")
# → "deliberative" после 5+ ходов, иначе None

confidence = store.get_confidence("user_42")
# → 0.0–1.0

summary = store.profile_summary("user_42")
# → {known, turn_count, dominant_mode, recent_dominant, confidence, mode_counts}
```

`recent_dominant_mode()` использует скользящее окно 20 ходов — отражает актуальный стиль, а не историческую привычку.

---

## Наблюдатель адекватности (SystemObserver)

### Патологии и коррекции

| Патология | Условие | Штраф score | Коррекция |
|-----------|---------|------------|-----------|
| `OVERHEATING` | mean > 0.82 | −0.15 | поле ×0.88 (включая resting) |
| `VACUUM` | max < 0.45 | −0.30 | resting +0.10, инжект якоря |
| `OSSIFICATION` | ось > 8 циклов + bias ≥ 0.80 | −0.20 | bias −0.30, ось −0.08 |
| `SPLIT_BRAIN` | два узла > 0.70 + разрыв < 0.05 | −0.25 | слабый −0.12 |
| `RUNAWAY_CHAOS` | chaos_trend < −0.30 | −0.20 | якорная ось +0.08 |
| `RESONANCE_COLLAPSE` | ось < 0.35 | −0.25 | экстренный +0.15 |

### Мета-самообучение

После 3 появлений той же патологии → `lesson:meta:{pathology}_pattern` (resonance 0.50–0.80).

### Ночной отчёт

```python
# В sleep consolidation:
report = observer.session_report(temporal_graph)
# {
#   "session_quality": "лёгкая" | "умеренная" | "тяжёлая",
#   "avg_adequacy": 0.85,
#   "total_cycles": 47,
#   "pathology_counts": {"OSSIFICATION": 3},
#   "lesson_nodes_injected": ["lesson:session:ossification"]
# }
```

---

## Периоды полураспада (кривая забывания)

| Тип узла | Half-life |
|----------|-----------|
| `lesson:*` | 24 часа |
| `lesson:meta:*` | 24 часа (наследует) |
| `lesson:session:*` | 24 часа (наследует) |
| `world:git:*` | 1 час |
| `world:error:*` | 30 минут |
| `world:custom:*` | 30 минут |
| `subconscious:*` | 10 минут |
| `world:critical:*` | 5 минут |

---

## Эволюция системы

```
v1  Реактивная:   запрос → mode_detector → ответ
v2  Подсознание:  + subconscious_loop (20с)
v3  Ось времени:  + TemporalGraph accumulation
v4  Самообучение: + velocity + quality feedback + reflection + WorldPoller
v5  5 сил:        + orientation ↔ TemporalGraph bidirectional + stabilization + decay + interference
v6  Наблюдатель:  + SystemObserver (Force 6) — adequacy guardian
v7  Граф+7 сил:   + causal edges + co-activation + Force 7 + predictive axis
                  + meta-lessons + session report + user profiles + feedback proxy
```

---

## Файлы системы

| Файл | Компонент |
|------|-----------|
| `hexagon_core/temporal_graph.py` | TemporalGraph, TemporalNode, все 7 сил |
| `hexagon_core/system_observer.py` | SystemObserver — мета-наблюдатель |
| `hexagon_core/user_profile.py` | UserProfileStore — профили пользователей |
| `agent/loop.py` | AgentLoop — subconscious/world потоки, feedback, user profiles |
| `agent/world_poller.py` | WorldPoller — git/logs → TemporalNodes |
| `coordinator/coordinator.py` | Coordinator.decide() — запускает все 7 сил |
| `orientation/center.py` | OrientationCenter — источник chaos/harmony сигналов |

## Тесты

| Файл | Тестов | Что покрывает |
|------|--------|--------------|
| `tests/unit/test_stabilization_forces.py` | 17 | Силы 3–5, stability_bias, trajectory |
| `tests/unit/test_orientation_force_ladder.py` | 11+ | Силы 1–2, co-activation, propagation |
| `tests/unit/test_system_observer.py` | 35 | Все 6 патологий + score + trend |
| `tests/unit/test_new_features.py` | 30 | Features 1–6 (causal graph, predictive axis, meta-lessons, user profiles, session report) |
| `tests/unit/test_world_poller.py` | 7 | WorldPoller |
| `tests/smoke/test_agent_loop.py` | 10 | Интеграционные тесты агента |
