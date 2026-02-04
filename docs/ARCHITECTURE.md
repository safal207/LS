# LS / Local Cognitive System (LCS) — Architecture

Этот документ описывает текущую архитектуру репозитория и то, как данные проходят через систему.

## High-Level Layers

1. **apps/** — приложения (entrypoints)
   - `apps/console/` — CLI runtime
   - `apps/ghostgpt/` — GUI overlay runtime

2. **python/modules/** — единый модульный слой
   - `audio/` → ingest/VAD
   - `stt/` → STT pipeline
   - `llm/` → LLM runtime (+ stability wrappers)
   - `agent/` → AgentLoop, cancellation, observability
   - `hexagon_core/` → когнитивное ядро (beliefs/causal/mission/COT)
   - `shared/` → config loader и общие утилиты

3. **config/** — единая конфигурация
   - `base.yaml` → common defaults
   - `{console,ghostgpt}.yaml` → app overrides
   - `local.yaml` → local overrides (ignored)

## Data Flow (Typical)

Console (упрощённо):

```
audio (file/chunks) → stt (text) → agent loop (state + cancellation) → llm (answer) → output
```

GhostGPT:

```
hotkey/UI events → audio/STT (text) → access protocol/agent loop → llm → panel update
```

## AgentLoop

`python/modules/agent/loop.py` — центральный “оркестратор” выполнения:
- управляет состояниями: `idle/listening/thinking/responding`
- умеет cooperative cancellation (new input supersedes current work)
- публикует метрики и события (best-effort)

### Observability Contract v1

События, которые уходят в sink, нормализуются к контракту `1.0`.

Файл: `python/modules/agent/event_schema.py`

Обязательные поля:
- `type`: `input|output|cancel|state_change|metrics`
- `timestamp`: `float` (epoch seconds)
- `task_id`: `str`
- `version`: `"1.0"`
- `state`: `str | null`
- `payload`: `dict`

## LLM Layer

`python/modules/llm/` содержит runtime и защитные слои:
- `breaker.py`: circuit breaker (опционально)
- `cot_adapter.py`: адаптер reasoning-ядра (опционально)
- `llm_module.py`: основной runtime

## Hexagon Core

`python/modules/hexagon_core/` — когнитивные примитивы и подсистемы:
- beliefs lifecycle (устойчивость знаний)
- temporal queries / indexing
- causal graph
- mission state

Важно: ядро не должно зависеть от UI.

## Где меняется “поведение”

1. `llm.system_prompt` в YAML (или overrides в `config/local.yaml`)
2. feature flags в `config/base.yaml`
3. настройки agent loop (cancellation, metrics, observability)

