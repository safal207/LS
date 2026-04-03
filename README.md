# GhostGPT — Local Cognitive System (LCS)

[English](#english) | [Русский](#russian)

---

<a name="english"></a>

# GhostGPT / LCS — Local Cognitive System

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](LICENSE)
[![Rust Powered](https://img.shields.io/badge/Rust-Inside-orange.svg)](#architecture)

**GhostGPT** is not a chatbot wrapper. It is a **cognitive operating system** for LLMs — an agent that thinks between your messages, learns from you continuously, and knows when it is not thinking clearly.

---

## What it actually does

Most AI agents answer and forget. GhostGPT **lives between answers**:

- While you type, a background subconscious thread analyses your conversation patterns
- When you reply with just "ok" after a long response, the system registers that as weak feedback
- When the same thinking mode appears three sessions in a row, it becomes a persistent memory node
- When the system detects it is stuck in one mode for too long, it corrects itself automatically

The result: an agent that develops a **cognitive character** over time and adapts it without being asked.

---

## Core Features

### Cognitive Field — 7 Forces

Every decision cycle runs 7 forces on the live knowledge graph (`TemporalGraph`):

| Force | What it does |
|-------|-------------|
| F1+F2 | Orientation: chaos/harmony signals reshape node resonance + associative propagation |
| F3 | Stabilization: nodes drift back to their natural resting level |
| F4 | Forgetting: nodes decay by type — lessons last 24h, urgent signals 5 min |
| F5 | Interference: competing cognitive modes cancel each other (no split-brain) |
| F6 | Observer: detects pathological states and self-corrects |
| F7 | Association: active nodes boost their linked neighbours |

### 6 Learning Mechanisms

The system learns from **four sources simultaneously**:

1. **Subconscious loop** (every 20s) — detects your thinking pattern (creative / deliberative / reactive) without asking
2. **Quality feedback** — explicit "да/нет" updates node resonance ±
3. **Feedback proxy** — long response + short reply = weak auto-negative signal
4. **Reflections** — after-action lessons ingested as 24h memory nodes
5. **World events** — git commits and error logs become temporal nodes
6. **Association graph** — co-activated nodes auto-strengthen their links

### Self-Monitoring (SystemObserver)

The observer runs every cycle and detects 6 pathological states:

| Pathology | Condition | Auto-correction |
|-----------|-----------|----------------|
| OVERHEATING | All nodes inflated | Normalize field ×0.88 |
| VACUUM | No active nodes | Lift floor + inject anchor |
| OSSIFICATION | Same axis for 8+ cycles | Reduce stability, nudge down |
| SPLIT_BRAIN | Two modes tied at high resonance | Suppress weaker by 0.12 |
| RUNAWAY_CHAOS | Chaos trend collapsing | Boost anchor axis |
| RESONANCE_COLLAPSE | Axis too weak to guide | Emergency boost |

After 3 occurrences of the same pathology → writes a `lesson:meta:*` memory node. The system remembers its own weaknesses.

### User Profiles

`UserProfileStore` tracks each user's cognitive style across sessions. After 5+ turns it provides a **starting hint** — the agent opens the next conversation already tuned to your style, using a 20-turn sliding window to catch recent drift.

### Predictive Axis

`predictive_axis(horizon_s=60)` — answers: *which node will be dominant in 60 seconds?* Based on current velocity, the system pre-warms for the incoming mode before it arrives.

### Multimodal Worker (optional)

`QwenOmniWorker` captures screen + audio context via DashScope Realtime API (or a safe fallback), stores insights as `ResonanceKnowledgeUnit`. Enabled via `QWEN_OMNI_ENABLED=1`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        AgentLoop                            │
│                                                             │
│  Subconscious (20s) ──►                                     │
│  WorldPoller     ──────►   TemporalGraph                    │
│  Quality FB      ──────►   (resonance nodes + causal edges) │
│  Auto Proxy      ──────►                                    │
│                               │                             │
│                    Coordinator.decide()                     │
│                    7 Forces per cycle                       │
│                               │                             │
│                    OrientationCenter ◄──► signal back       │
│                                                             │
│  Sleep consolidation → session_report → lesson:session:*   │
└─────────────────────────────────────────────────────────────┘
```

**Stack:**
- Python layer — agent orchestration, cognitive field, GUI (Qt6)
- Rust core — high-performance pattern matching, SIMD vector search
- Hexagon Core — beliefs, causal memory, temporal graph, orientation

---

## Quick Start

### Prerequisites
- Python 3.9+
- Rust & Cargo (for Rust core)
- [Ollama](https://ollama.com/) (local LLM inference)

### Install

```bash
# Users
pip install "ghostgpt-core[full]"

# Developers
git clone https://github.com/safal207/LS.git
cd LS
python -m venv venv && source venv/bin/activate
pip install -e ".[full]"
maturin develop  # build Rust core
```

### Launch

```bash
# GUI
python apps/ghostgpt/main.py

# Console
python apps/console/main.py

# Multi-agent demo (3 coordinated agents)
python -m apps.multi_agent_demo
```

### Optional: Multimodal worker

```bash
export QWEN_OMNI_ENABLED=1
export DASHSCOPE_API_KEY=your_key   # omit for fallback mode
python apps/ghostgpt/main.py
```

---

## Repository Structure

```
apps/
  console/            CLI entrypoint
  ghostgpt/           GUI entrypoint
python/
  modules/
    agent/            AgentLoop + subconscious + world poller
    hexagon_core/     TemporalGraph, SystemObserver, UserProfileStore
    coordinator/      Coordinator (7 forces), ModeDetector
    orientation/      OrientationCenter, RhythmEngine
    graph/            MemoryGraphStore, ResonanceKnowledgeUnit, CareCycle
    omni/             QwenOmniWorker (multimodal background worker)
    llm/              LLM pipeline (Ollama / Groq / Qwen)
    shared/           Config, EventBus, plugins
  tests/
    unit/             Unit tests for all cognitive subsystems
    smoke/            Integration tests for AgentLoop
config/
  base.yaml           Shared config
  console.yaml        Console overrides
  ghostgpt.yaml       GUI overrides
  local.yaml          Local secrets (gitignored)
```

---

## Configuration

Layered YAML: `base → app → local`

```python
from shared.config_loader import load_config
cfg = load_config("console")
```

Key env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `QWEN_OMNI_ENABLED` | `0` | Enable multimodal background worker |
| `DASHSCOPE_API_KEY` | — | DashScope key (omit for fallback mode) |
| `GRAPH_MEMORY_STORE_PATH` | `data/graph_memory/cases.jsonl` | Memory store path |
| `ENABLE_QUERY_REWRITING` | `true` | Rewrite queries before vector search |
| `LS_REPO_PATH` | `cwd` | Repo path for WorldPoller git monitoring |

---

## Tests

```bash
# All unit tests (direct — no pytest lthread conflict)
python3 tests/unit/test_stabilization_forces.py
python3 tests/unit/test_system_observer.py
python3 tests/unit/test_new_features.py
python3 tests/unit/test_orientation_force_ladder.py
python3 tests/unit/test_world_poller.py

# Qwen Omni + memory store
pytest python/tests/test_qwen_omni_worker.py
pytest python/tests/test_memory_store_locking.py
```

| Test file | Tests | Covers |
|-----------|-------|--------|
| `test_stabilization_forces.py` | 17 | Forces 3–5, stability_bias, trajectory |
| `test_system_observer.py` | 35 | All 6 pathologies, score, trend |
| `test_new_features.py` | 30 | Causal graph, predictive axis, meta-lessons, user profiles, session report |
| `test_orientation_force_ladder.py` | 11+ | Forces 1–2, co-activation, propagation |
| `test_world_poller.py` | 7 | WorldPoller git/logs |
| `test_qwen_omni_worker.py` | 4 | Multimodal worker fallback + store |

---

## Documentation

| File | Contents |
|------|---------|
| [COGNITIVE_FIELD_COMPLETE.md](COGNITIVE_FIELD_COMPLETE.md) | Full 7-force architecture, learning mechanisms, all APIs |
| [SUBCONSCIOUS_TEMPORAL_LOOP.md](SUBCONSCIOUS_TEMPORAL_LOOP.md) | Subconscious loop + feedback loop diagram |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data flow and system components |
| [docs/architecture/layers.md](docs/architecture/layers.md) | Full 12-layer catalogue |
| [FINAL_PROJECT_REPORT.md](FINAL_PROJECT_REPORT.md) | Golden Master overview |

---

## How it differs from other agents

| | Typical agent | GhostGPT |
|--|---------------|----------|
| Between messages | Idle | Subconscious analysis running |
| Learning | On request | Continuous (4 sources) |
| Memory | Flat history | Weighted resonance graph with decay |
| Self-awareness | None | Observer detects + corrects pathologies |
| User model | None | Per-user profile, mode prediction |
| Failure mode | Silent drift | Detected and self-corrected |

---

© 2026 GhostGPT Team. Strictly Local. Strictly Cognitive.

---

<a name="russian"></a>

# GhostGPT — Локальная когнитивная система

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)

GhostGPT — это не обёртка над ChatGPT. Это **когнитивная операционная система** для LLM: агент, который думает между твоими сообщениями, учится у тебя непрерывно и знает, когда сам с собой не в порядке.

---

## Что это такое простыми словами

Обычный ИИ: вопрос → подумал → ответил → забыл.

GhostGPT **живёт между ответами**:
- Пока ты печатаешь, фоновый поток анализирует твой стиль мышления
- Когда ты ответил коротко после длинного ответа агента — это сигнал "не попал"
- Когда один режим мышления повторяется раз за разом — он становится долгосрочной памятью
- Когда система слишком долго стоит на одном месте — она сама себя исправляет

Итог: агент с **когнитивным характером**, который развивается без явных инструкций.

---

## Ключевые компоненты

### Когнитивное поле — 7 сил

В каждом цикле `Coordinator.decide()` на граф знаний действуют 7 сил:

| Сила | Что делает |
|------|-----------|
| F1+F2 | Ориентация: chaos/harmony изменяют резонанс + ассоциативная проводимость |
| F3 | Стабилизация: узлы возвращаются к своему "положению покоя" |
| F4 | Забывание: уроки живут 24ч, критические сигналы — 5 минут |
| F5 | Интерференция: конкурирующие режимы подавляют друг друга |
| F6 | Наблюдатель: обнаруживает патологии и корректирует поле |
| F7 | Ассоциация: активные узлы усиливают связанных соседей |

### 6 механизмов обучения

Система учится **одновременно из 4 источников**:

1. **Подсознание** (каждые 20с) — определяет твой режим мышления без вопросов
2. **Явная обратная связь** — "да/нет" обновляет резонанс узла ±
3. **Авто-прокси** — длинный ответ + короткая реакция = авто-негативный сигнал
4. **Рефлексии** — уроки после действий, хранятся 24ч
5. **Внешние события** — git-коммиты и ошибки в логах становятся узлами памяти
6. **Ассоциативный граф** — совместно активированные узлы укрепляют связи

### Наблюдатель адекватности

`SystemObserver` работает каждый цикл и детектирует 6 патологий:

| Патология | Условие | Коррекция |
|-----------|---------|----------|
| OVERHEATING | Все узлы перегреты | Нормализация поля ×0.88 |
| VACUUM | Нет активных узлов | Поднять пол + инжект якоря |
| OSSIFICATION | Одна ось 8+ циклов | Снизить инерцию, сдвинуть вниз |
| SPLIT_BRAIN | Два режима в клинче | Подавить слабый на 0.12 |
| RUNAWAY_CHAOS | Коллапс хаоса | Буст якорной оси |
| RESONANCE_COLLAPSE | Ось слишком слабая | Экстренный буст |

После 3 повторений патологии → пишет `lesson:meta:*`. **Система запоминает свои слабости.**

### Профили пользователей

`UserProfileStore` отслеживает когнитивный стиль каждого пользователя. После 5+ ходов даёт **стартовый хинт** — агент начинает следующий разговор уже настроенным на твой стиль. Скользящее окно 20 ходов ловит изменения стиля.

---

## Архитектура

```
AgentLoop
  ├── Subconscious loop (20s)  ─►
  ├── WorldPoller (git/logs)   ─►  TemporalGraph
  ├── Quality feedback         ─►  (узлы + рёбра)
  └── Auto feedback proxy      ─►
                                    │
                          Coordinator.decide()
                          7 сил за цикл
                                    │
                          OrientationCenter ◄──► сигнал обратно
                                    │
                    sleep → session_report → lesson:session:*
```

---

## Быстрый старт

```bash
git clone https://github.com/safal207/LS.git
cd LS
python -m venv venv && source venv/bin/activate
pip install -e ".[full]"

# GUI
python apps/ghostgpt/main.py

# Консоль
python apps/console/main.py
```

### Мультимодальный воркер (опционально)

```bash
export QWEN_OMNI_ENABLED=1
export DASHSCOPE_API_KEY=your_key   # без ключа — fallback режим
python apps/ghostgpt/main.py
```

---

## Документация

| Файл | Содержимое |
|------|-----------|
| [COGNITIVE_FIELD_COMPLETE.md](COGNITIVE_FIELD_COMPLETE.md) | Полная архитектура 7 сил и 6 механизмов обучения |
| [SUBCONSCIOUS_TEMPORAL_LOOP.md](SUBCONSCIOUS_TEMPORAL_LOOP.md) | Подсознание + петля обратной связи |
| [docs/architecture/layers.md](docs/architecture/layers.md) | Каталог 12 архитектурных слоёв |
| [FINAL_PROJECT_REPORT.md](FINAL_PROJECT_REPORT.md) | Итоговый отчёт Golden Master |

---

## Сравнение с другими агентами

| | Обычный агент | GhostGPT |
|--|---------------|----------|
| Между сообщениями | Простаивает | Подсознание работает |
| Обучение | По запросу | Непрерывно (4 источника) |
| Память | Плоская история | Граф с резонансом и распадом |
| Самоконтроль | Нет | Наблюдатель корректирует патологии |
| Модель пользователя | Нет | Профиль + предсказание режима |
| Отказ | Тихий дрейф | Обнаруживается и исправляется |

---

© 2026 GhostGPT Team. Strictly Local. Strictly Cognitive.
