# GhostGPT (LCS) — Local Cognitive System

[English](README.md#english) | [Русский](README.md#russian)

---

<a name="english"></a>

# GhostGPT / LCS — Local Cognitive System

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](LICENSE)
[![Rust Powered](https://img.shields.io/badge/Rust-Inside-orange.svg)](#architecture)

**GhostGPT** (built on the **Local Cognitive System** architecture) is an advanced cognitive layer for Large Language Models. It provides a persistent agentic loop, temporal context, and cross-session memory, enabling LLMs to behave as long-running autonomous entities.

**Interview Copilot (Ghost Mode)** is one of the primary applications powered by this core.

## 🚀 Key Features

- **AgentLoop**: Sophisticated state management (`idle/listening/thinking/responding`) with cooperative cancellation and memory hooks.
- **12-Layer Cognitive Architecture**: Including Metabolism (knowledge processing), Amygdala (emotional balance), and Sleep/Homeostasis (memory consolidation).
- **Rust Optimization Layer**: High-performance pattern matching and SIMD-accelerated vector search for real-time responsiveness.
- **Temporal Memory**: A graph-based belief system that tracks the evolution of knowledge over time.
- **Reasoning Diff**: Compare agent reasoning traces and detect divergence points.
- **Local-First & Privacy-Centric**: Designed to run entirely on your hardware with built-in PII redaction and safety gates.
- **Web4 Integration**: Ready for the next generation of decentralized AI protocols.
- **AI Venture Engine + PFC**: Portfolio-level admission, stage-gate, and capital allocation controls for turning idea flow into execution throughput.

## 🛠 Architecture

GhostGPT follows a modular **Hexagon Core** design:
- **Python Layer**: Handles high-level logic, GUI (Qt6), and agent orchestration.
- **Rust Core**: Low-level optimizations for vision processing, memory management, and high-speed data transport.

## 📦 Quick Start

### Prerequisites
- **Python 3.9+**
- **Rust & Cargo** (for building core optimizations)
- [**Ollama**](https://ollama.com/) (recommended for local LLM inference)

### Installation

```bash
# For users
pip install "ghostgpt-core[full]"

# For developers / contributors
git clone https://github.com/safal207/LS.git
cd LS
python -m venv venv
source venv/bin/activate
pip install -e ".[full]"
```

> **Note:** `ghostgpt-core` is a core library.
> The GUI (`apps/ghostgpt/main.py`) and console (`apps/console/main.py`)
> require cloning the repository and running from source.

### Build Rust Core (for developers)

```bash
maturin develop
```

### Launch

**GUI Dashboard (GhostGPT):**
```bash
python apps/ghostgpt/main.py
```

**Console Mode:**
```bash
python apps/console/main.py
```

## 📚 Documentation

- [Final Project Report](FINAL_PROJECT_REPORT.md) — Comprehensive overview of the system.
- [Architecture Deep Dive](docs/ARCHITECTURE.md) — Data flow and system components.
- [Web4 Overview](docs/WEB4_OVERVIEW.md) — Vision for the decentralized future.
- [HCP & CIP Specs](docs/HCP_SPEC.md) — Protocol specifications for human and agent interactions.
- [AI Venture Engine Positioning](docs/AI_VENTURE_ENGINE_PFC_POSITIONING.md) — Product documentation and marketing positioning for Portfolio Flow Controller.


## ⚡ LLM Speed Evolution (Python / Rust / C++)

We now publish repeatable acceleration benchmarks for the interview-copilot streaming path:

- Fast connect + high-speed guide: [`docs/FAST_CONNECT_AND_PERFORMANCE.md`](docs/FAST_CONNECT_AND_PERFORMANCE.md)
- Roadmap: [`docs/LLM_ACCELERATION_ROADMAP.md`](docs/LLM_ACCELERATION_ROADMAP.md)
- Latest benchmark report: [`docs/online_interview_llm_latency_results.md`](docs/online_interview_llm_latency_results.md)
- Architecture review: [`docs/online_interview_llm_latency_review.md`](docs/online_interview_llm_latency_review.md)

Current snapshot includes:
- TTFT comparison (streaming vs non-streaming),
- Parser micro-benchmark (Python vs Rust vs C++),
- practical startup path for fastest connect and response.


## Reasoning Diff

Reasoning Diff allows developers to compare two reasoning traces and detect where agent decisions diverged.

### Why it matters

AI debugging often requires comparing:
- a working reasoning path;
- a failed reasoning path.

Reasoning Diff highlights the divergence point so you can quickly isolate where the run started to drift, including potential hallucination branches.

### Visual example

Trace A (success)
`start → plan → execute → verify → finish`

Trace B (failure)
`start → plan → execute → assumption → hallucination → contradiction`

Diff output:

```text
start
plan
execute
--- divergence detected ---
verify
vs
assumption
```

The system highlights the first conflicting transition, then lets you inspect the branches that follow.

### CLI-style usage

```bash
ltp diff trace-success.json trace-failure.json
```

Example output:

```text
Comparing reasoning traces...

Shared path:
start → plan → execute

Divergence point:
Trace A: verify
Trace B: assumption

Possible hallucination path detected.
```

### Developer example (TypeScript)

```ts
const diff = ReasoningDiff.compare(traceA, traceB)

console.log(diff.sharedPath)
console.log(diff.divergencePoint)
console.log(diff.branchA)
console.log(diff.branchB)
```

This gives developers a compact way to inspect how two runs split and which branch introduced unstable reasoning.

### Comparing successful vs failed reasoning

Common debugging flow:
1. Agent run succeeds.
2. Another run fails.
3. Developer compares traces.
4. Reasoning Diff highlights divergence.

### Relation to Reasoning State Graph

Reasoning Diff operates on the Reasoning State Graph and extends Trace Replay capabilities.
Because reasoning is represented as a graph of transitions, the system can:
- compare paths;
- detect divergence;
- visualize alternate reasoning routes.

Together with trace, replay, and rewind capabilities, Reasoning Diff completes the core AI reasoning observability toolkit.

---

<a name="russian"></a>

# LS — Local Cognitive System (LCS)

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Python tests](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Rust build](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)

LS (Local Cognitive System) — локальная когнитивная система: архитектурный слой поверх LLM, который добавляет агентный цикл, временной контекст, устойчивость и наблюдаемость.

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)
[![Local--first](https://img.shields.io/badge/Architecture-Local--first-success.svg)](#ls--local-cognitive-system-lcs)

Интервью‑копайлот (Ghost Mode) — **один из режимов/приложений**, а не “ядро” проекта.

Документация:
- `FINAL_PROJECT_REPORT.md` — основной итоговый отчёт по Golden Master
- `docs/MANIFESTO.md` — позиционирование и принципы
- `docs/ARCHITECTURE.md` — архитектура и поток данных
- `docs/CIP_SPEC.md` — Cognitive Interlink Protocol (агент‑агент)
- `docs/HCP_SPEC.md` — Human Connection Protocol (человек‑агент)
- `docs/LIP_SPEC.md` — Liminal Internet Protocol (обучение из интернета)
- `docs/WEB4_OVERVIEW.md` — обзор Web4
- `docs/WHITEPAPER_WEB4.md` — whitepaper Web4
- `docs/RFC_BUNDLE_WEB4.md` — единый RFC‑bundle
- `docs/RUST_TRANSPORT_SPEC.md` — спецификация Rust‑транспорта
- `docs/ARCH_DIAGRAMS.md` — архитектурные диаграммы (Mermaid)
- `docs/ROADMAP.md` — дорожная карта
- `docs/FAST_CONNECT_AND_PERFORMANCE.md` — быстрый старт и high-speed режим для пользователей
- `docs/INVESTMENT_ANALYSIS_RU.md` — инвестиционный анализ и рекомендации по позиционированию
- `docs/AI_VENTURE_ENGINE_PFC_POSITIONING.md` — документация и маркетинговое позиционирование AI Venture Engine + PFC
- `docs/architecture/layers.md` — полный каталог 12 архитектурных слоев (v1.1)
- `docs/MODEL_ECONOMY_LAYER.md` — MEL: экономика моделей, реестр, metering и revenue split
- `schemas/*.schema.json` — формальные JSON Schema протоколов

## Архитектура GhostGPT (Март 2026)

GhostGPT v1.1 базируется на **12-слойной когнитивной архитектуре**, объединяющей восприятие, эмоциональный баланс (Amygdala), метаболизм знаний и глубокую консолидацию во сне.

Подробное описание: [docs/architecture/layers.md](docs/architecture/layers.md).

Ключевые инновации v1.1:
- **Metabolism Layer**: Переработка когнитивного опыта в энергию роста.
- **Immune & Safety**: Адаптивная защита и "антитела" против инъекций.
- **Sleep & Homeostasis**: Консолидация памяти и очистка "токсинов" во сне.

*Дополнительные экспериментальные подсистемы (Bloodstream, Self-Healing) вынесены в отдельный раздел документации.*

## Структура репозитория

```
apps/
  console/   # CLI entrypoint
  ghostgpt/  # GUI entrypoint
python/
  modules/
    agent/          # AgentLoop + observability
    audio/          # аудио ingest
    stt/            # STT пайплайн
    llm/            # LLM пайплайн
    shared/         # shared utils + config loader
    hexagon_core/   # когнитивное ядро (beliefs/causal/mission/COT)
config/
  base.yaml
  console.yaml
  ghostgpt.yaml
  local.yaml (ignored)
```

## Что даёт LCS

- **AgentLoop**: состояния `idle/listening/thinking/responding`, cooperative cancellation, memory hooks, метрики.
- **Temporal/Belief foundation**: жизненный цикл убеждений и temporal‑индекс в `hexagon_core`.
- **Stability layer**: circuit breaker для LLM вызовов.
- **Observability**: event sink + строгий event‑contract (версия `1.0`).
- **Единый конфиг**: YAML `base → app → local` через `shared.config_loader`.

## Какая боль рынка мы закрываем

- **Недоверие к AI‑решениям в бизнесе**: нет прозрачного протокола для подтверждения фактов, источников и авторства решений.
- **Фрагментация агентных систем**: разные команды создают несвязанные агенты без общего trust‑ и state‑слоя.
- **Эскалация галлюцинаций**: ошибки распространяются между продуктами, потому что нет коллективной валидации знаний.
- **Отсутствие когнитивного контекста**: системы не знают о нагрузке, фокусе и намерении друг друга, из‑за чего UX деградирует.
- **Слабый слой согласия человека**: нет протокольного уровня для intent/consent/safety, который уважает человека.
- **Зависимость от централизованных платформ**: локальные команды теряют автономию и контроль над доверительной моделью.

## Quick Start

### Требования
- Python 3.9+
- [Ollama](https://ollama.com/) (локальная LLM-служба)

### Installation

```bash
# Для пользователей
pip install "ghostgpt-core[full]"

# Для разработчиков / контрибьюторов
git clone https://github.com/safal207/LS.git
cd LS
python -m venv venv
source venv/bin/activate
pip install -e ".[full]"
```

> **Примечание:** `ghostgpt-core` — это библиотека ядра.
> GUI и консольный режим запускаются только из клонированного репозитория,
> не через `pip install`.

## Multi-Agent Demo

Запустите 3 параллельных агента, координирующихся через общую память:

```bash
python -m apps.multi_agent_demo
```

Агенты будут задавать вопросы и получать контекст из ответов друг друга.

## Конфигурация

Конфиги в YAML:
- `config/base.yaml` — общие параметры
- `config/console.yaml` — overrides для консоли
- `config/ghostgpt.yaml` — overrides для GUI
- `config/local.yaml` — локальные override (ignored)

Loader находится в `python/modules/shared/config_loader.py`:
```python
from shared.config_loader import load_config
cfg = load_config("console")
```

Также работает совместимый импорт:
```python
from modules.shared.config_loader import load_config
```

Для локальных настроек используйте шаблон:
```
config/local.example.yaml
```
Скопируйте его в `config/local.yaml` и внесите свои значения (ключи, модели и т.п.).

Переменная окружения `ENABLE_QUERY_REWRITING` управляет переписыванием пользовательского запроса перед векторным поиском (`true/1/yes` по умолчанию).
Для полного отключения set `ENABLE_QUERY_REWRITING=false` (полезно для локальной отладки и тестов).

## Режимы (в т.ч. Interview Mode)

Поведение системы в первую очередь задаётся `llm.system_prompt` (см. `config/base.yaml` и overrides в `config/local.yaml`).

Если нужен “интервью‑режим”, задайте системный промпт в `config/local.yaml` (пример):
```yaml
llm:
  system_prompt: |
    You are a senior developer interviewing candidates.
    Provide concise, bullet-point answers suitable for technical interviews.
    Answer in Russian.
```

## Модули

Единый модульный слой находится в `python/modules/`:
- `agent/` — AgentLoop и observability
- `audio/` — ingest/VAD
- `stt/` — Whisper обработка
- `llm/` — генерация ответов (Ollama/Groq/Qwen)
- `shared/` — общие утилиты и конфиг
- `hexagon_core/` — когнитивное ядро агента

## Smoke‑тесты

```bash
python apps/console/main.py
python apps/ghostgpt/main.py
python -c "from modules.shared.config_loader import load_config; print(load_config('console'))"
python scripts/smoke.py
```

## Примечания

- Все вычисления — локально (кроме опционального cloud‑fallback, если включён).
- Для системного аудио на Windows обычно нужен VB‑Cable или включенный Stereo Mix (зависит от железа/драйверов).

## Resonance v3
- Используется sentence-transformers (`all-MiniLM-L6-v2`) для точной семантики
- Глобальный LRU-кэш эмбеддингов (макс. 10 000 записей)
- Настраиваемый `min_similarity` (по умолчанию 0.35)
- Логи при загрузке модели и cache miss


## Evaluation

Запуск standalone-оценки Resonance v3:

```bash
python eval/evaluate_resonance.py
```

Вывод:
- `eval/results/resonance_eval.json`

Env:
- `ENABLE_REWRITING_IN_EVAL=false` — отключить rewriting в режиме `rewritten`.

Метрики:
- `hit_rate` — доля вопросов, где найдены чанки выше `min_similarity`.
- `avg_similarity` — средняя similarity по всем найденным score.
- `top_score` — максимальный score среди найденных чанков.
- `chunks_found` — число чанков выше порога.
- `latency_ms` — задержка обработки вопроса.

---
© 2026 GhostGPT Team. Strictly Local. Strictly Cognitive.

## Adaptive Plugin & Monitoring System

Новый архитектурный слой добавляет hot-load плагинов и централизованный мониторинг.

### Плагины

- Директория плагинов: `python/plugins/`.
- Контракт плагина:

```python
class Plugin:
    name: str
    def setup(ctx: RuntimeContext) -> None: ...
    def shutdown(ctx: RuntimeContext) -> None: ...
```

- Менеджер: `PluginManager` (`python/modules/shared/plugin_manager.py`):
  - `load_all()` — загружает все плагины из `python/plugins/*.py` без рестарта приложения.
  - `load_from_path(path)` — загружает конкретный плагин.
  - `reload(name)` — безопасно перезагружает плагин на лету.
  - `unload(name)` — выгружает плагин и очищает его сервисы/подписки.
- Изоляция: ошибки плагина не останавливают агент; публикуются lifecycle-события `plugin_failed`, `plugin_load_failed`, `plugin_shutdown_failed`.
- Права плагинов: `PluginPermissions` (filesystem/network/process) с deny-by-default политикой в `PluginManager`.

Пример:

```python
from modules.shared.bootstrap import bootstrap_app
from modules.shared.plugin_manager import PluginManager

ctx = bootstrap_app(__file__, "console")
pm = PluginManager(ctx)
pm.load_all()
```

### Мониторинг

- Сервис: `MonitorService` (`python/modules/shared/monitoring.py`).
- Регистрация в runtime:

```python
monitor = MonitorService(ctx)
monitor.register()  # ctx.services.register("monitor", monitor)
```

- API:
  - `get_queue_stats()` — размер/емкость/utilization/throughput очередей (`llm_queue`, `ui_queue`, `audio_queue`).
  - `get_resource_usage()` — CPU, RAM, диск.
  - `get_event_bus_stats()` — число подписчиков EventBus.
  - `subscribe_alert(event_type, callback)` — подписка на алерты (`queue_high_utilization`, `llm_timeout`).

Пример:

```python
monitor = ctx.services.get("monitor")
stats = monitor.snapshot()
print(stats["queues"], stats["resources"], stats["event_bus"])
```


CLI-утилита для операционного управления плагинами:

```bash
python apps/console/plugins_cli.py list
python apps/console/plugins_cli.py load --path python/plugins/echo_plugin.py
python apps/console/plugins_cli.py reload echo_plugin
python apps/console/plugins_cli.py unload echo_plugin
```

`EventBus` также поддерживает неблокирующий dispatch через `publish_async(event)`.


## Cognitive Loop & Memory Graph

Добавлен новый когнитивный runtime-модуль (`python/ls/`) с:
- `ls.memory.MemoryGraph` для граф-памяти (nodes/edges/search/context),
- `ls.cognition.ReflectionEngine` для state comparison, progress score и self-reflection,
- JSON persistence через `JsonGraphStore` (`data/memory_graph.json`).

Подробная архитектура и цикл: `docs/cognitive_loop.md`.
