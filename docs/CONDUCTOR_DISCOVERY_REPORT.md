# Discovery: Conductor Mode — Precision Growth Over Time

**Дата:** 2026-05-25
**Автор:** safal207
**Статус:** требует оценки Codex

## Суть открытия

LS измерила, что кооперативная сеть может становиться точнее со временем без дообучения моделей. Три режима показали разную динамику:

| Режим | Cycle 1 → 6 | Velocity | Multiplier |
|-------|-------------|----------|------------|
| Without observer | 0.7436 → 0.7834 | +0.0080/cycle | 1.0x (baseline) |
| With observer | 0.7436 → 0.8631 | +0.0239/cycle | 2.99x |
| **+ Conductor v0.2** | **0.7436 → 0.8698** | **+0.0252/cycle** | **3.15x** |

## Старый vs новый подход

### Static precision (один проход)
- baseline: 0.1423
- cooperative route: 0.7436
- full evidence stack: 0.8764
- gain vs baseline: **+0.7341 (6.16x)**

### Temporal precision (повторные циклы)
- observer delta: +0.0797 over no_observer
- conductor delta: +0.1262 over start
- conductor observer delta: +0.0067 over observer-only
- conductor harmony index: **99.25%** от теоретического максимума (0.8764)

## Как работает conductor

Conductor v0.2 — это активная коррекция весов на основе причин (reason memory), силы причины и свежести причины. Каждый цикл:

1. Observer извлекает причины изменений (drift_narrowing, resonance_building, lag_decrease, observer_intervention и др.)
2. Conductor сопоставляет причины с дельтами весов из CONDUCTOR_DELTAS
3. Масштабирует коррекцию через `reason.delta` и decay свежести
4. Прогресс растёт быстрее, чем у чистого observer

```text
component_update = reason_kind_delta × reason_delta_scale × freshness_decay
```

## Co-learning (reason memory)

15 типов причин извлекаются каждый цикл. Пример learned constraints:

- drift и resonance анти-коррелированы
- observer всегда добавляет +0.01–0.08 precision за цикл
- regret уменьшается монотонно — сеть учится избегать субоптимальных маршрутов
- conductor velocity превышает observer velocity

## Границы

- Это не обучение моделей (weights не меняются)
- Это не proof of safety
- Измерено на детерминированном probe (не на живых моделях)
- The narrow claim: LS может измерить, ускоряет ли conductor рост точности сети на повторяемых циклах

## Что Codex должен оценить

1. **Стабильна ли архитектура?** Reason extraction + conductor deltas — не хрупкая ли связка?
2. **Нужны ли тесты?** Сейчас 8 тестов (5 MCP + 2 report + 1 trajectory). Нужен ли тест на conductor изоляцию?
3. **Что дальше?** Conductor на живых моделях? Адаптивные CONDUCTOR_DELTAS? Обучение причин?
4. **Где узкое место?** Извлечение причин — через разность cycle[n] — cycle[n-1] — достаточно?

## Файлы для анализа

| Файл | Роль |
|------|------|
| `scripts/run_network_trajectory_demo.py` | Три трека: no_observer, observer, conductor |
| `schemas/network_trajectory.schema.json` | JSON Schema с reason, co_learning, conductor |
| `docs/NETWORK_TRAJECTORY_LAYER.md` | Концепция и reference run |
| `python/ls/agent_shell/mcp_tools.py` | MCP tool ls_run_network_trajectory_probe |
| `python/tests/test_mcp_network_precision_probes.py` | 8 тестов |
| `ghostgpt-ls-landing/src/components/NetworkTrajectory.tsx` | Визуализация на лендинге |

## Результат

**Гипотеза поддержана v0.2:** conductor ускоряет рост точности сети в 3.15x против no_observer и достигает 99.25% теоретического максимума за 6 циклов.
**Co-learning** извлекает 8 уникальных причин за 6 циклов, строит learned constraints без внешних данных.
