# LS — Local-First Coordination and Oversight Runtime

[English](#english) | [Русский](#russian)

---

<a name="english"></a>

# LS — Local-First Coordination and Oversight Runtime

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Council Safety Gate](https://github.com/safal207/LS/actions/workflows/council_safety.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/council_safety.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](LICENSE)
[![Rust Powered](https://img.shields.io/badge/Rust-Inside-orange.svg)](#core-architecture-summary)

Live site: [GitHub Pages](https://safal207.github.io/LS/)

**LS is a local-first coordination and oversight runtime for human-plus-model systems.**
It records council cycles, tracks contribution and receiver resonance, exposes approval-safe operator workflows, and produces replayable artifacts for evaluation and governance.
Instead of treating model output as a black box, LS turns decision cycles into measurable, reviewable, and improvable runtime artifacts.

---

## Why LS exists

Most AI systems produce answers but do not preserve reviewable structure around:

- who participated,
- which route was chosen,
- what was adopted,
- whether the receiver accepted the outcome cleanly,
- and where human approval was applied.

LS exists to make model-assisted coordination inspectable and measurable by default, not only after incidents.

## What LS is in practical terms

LS is an **operator-facing runtime shell** around model-assisted decision cycles:

- runs council-style cycles instead of a single opaque completion,
- records cycle-level artifacts for replay and post-hoc review,
- measures contribution, merit, and receiver-resonance signals,
- supports human approval and governance-safe operator intervention,
- emits quality-gated outputs suitable for evaluation, benchmarks, and evidence packages.

## Evidence surface (proof of behavior)

The repository already exposes a concrete evidence layer:

- **Replayable traces** for task and council inspection
- **Council result artifacts** with structured cycle outputs
- **Contribution / merit / resonance signals** (`CouncilContributionLedger`, `CEL`)
- **Quality gates and machine-readable reports** (`LiminalQA`, CI thresholds)
- **Benchmark snapshots** and interpretation notes under [`benchmark/`](benchmark/)
- **Council Safety Gate in CI** for risk-aware review enforcement

If you are evaluating this repo, start by checking these artifacts before reading internal mechanism details.

## Safety and oversight relevance

LS is positioned as oversight infrastructure, not convenience prompting UX.

Safety-relevant surfaces include:

- measurable model participation and adoption,
- replayable cycle traces and post-hoc inspection,
- approval-safe operator workflows,
- quality-gated outputs and CI enforcement,
- packaging for benchmark/dataset/demo artifacts.

Primary positioning doc:

- [`docs/SAFETY_PROGRAMS_POSITIONING.md`](docs/SAFETY_PROGRAMS_POSITIONING.md)

## What reviewers should understand first

A reviewer should understand, quickly:

1. this project is about **oversight**, not generic assistant polish;
2. this repo contains **real engineering artifacts**, not only conceptual framing;
3. LS already emits **measurable traces, scorecards, and evaluation outputs**;
4. the outputs can plausibly become a **benchmark, dataset, or reproducible demo artifact**.

## Best reviewer path

For program, grant, fellowship, or technical-review contexts:

1. [README.md](README.md)
2. [`docs/SAFETY_PROGRAMS_POSITIONING.md`](docs/SAFETY_PROGRAMS_POSITIONING.md)
3. [`docs/FELLOWSHIP_APPLICATION_READY.md`](docs/FELLOWSHIP_APPLICATION_READY.md)
4. [`docs/FELLOWSHIP_DEMO_PATH.md`](docs/FELLOWSHIP_DEMO_PATH.md)
5. [`benchmark/README.md`](benchmark/README.md)
6. [`benchmark/RESULTS.md`](benchmark/RESULTS.md)

## How LS differs from typical agents

| | Typical agent | LS |
|--|---------------|----|
| Primary output | answer text | council-cycle artifact + answer |
| Reviewability | limited chat history | replayable traces + structured fields |
| Participation accounting | usually absent | contribution / merit / resonance tracking |
| Approval workflow | ad hoc | explicit operator approval-safe path |
| Governance posture | optional | built into runtime + CI safety gate |
| Evaluation surface | one-off prompt tests | quality gates + benchmark snapshots |

## Core architecture summary

```
┌────────────────────────────────────────────────────────────────┐
│                          AgentLoop                             │
│                                                                │
│  Subconscious (20s)  ────►                                     │
│  WorldPoller (git)   ────►  TemporalGraph                      │
│  Quality FB          ────►  (resonance nodes + causal edges)   │
│  Auto Proxy          ────►                                     │
│                                │                               │
│                     Coordinator.decide()                       │
│                     7 Forces per cycle                         │
│                                │                               │
│                     OrientationCenter ◄──► signal back         │
│                                                                │
│  Council artifacts / traces / score updates / review outputs   │
└────────────────────────────────────────────────────────────────┘
```

**Stack:**
- Python layer — orchestration, councils, CLI/GUI, quality/evaluation hooks
- Rust core — high-performance pattern matching and vector operations
- Hexagon core — temporal graph, resonance memory, observer logic

## Cognitive field internals (supporting mechanism)

The cognitive architecture remains important, but it is a supporting mechanism for the oversight runtime.

### Cognitive Field — 7 Forces

Every decision cycle runs 7 forces on the live knowledge graph (`TemporalGraph`):

| Force | What it does |
|-------|-------------|
| F1+F2 | Orientation: chaos/harmony signals reshape node resonance + associative propagation |
| F3 | Stabilization: nodes drift back to their natural resting level |
| F4 | Forgetting: nodes decay by type — lessons last 24h, urgent signals 5 min |
| F5 | Interference: competing cognitive modes cancel each other |
| F6 | Observer: detects pathological states and self-corrects |
| F7 | Association: active nodes boost linked neighbours |

### Learning and self-monitoring

- subconscious loop (20s), explicit/implicit feedback, reflections, world events,
- pathology detection and auto-correction via `SystemObserver`,
- persistent user profile adaptation and predictive axis hints.

Detailed internals:
- [COGNITIVE_FIELD_COMPLETE.md](COGNITIVE_FIELD_COMPLETE.md)
- [SUBCONSCIOUS_TEMPORAL_LOOP.md](SUBCONSCIOUS_TEMPORAL_LOOP.md)

## Multimodal operator runtime (secondary extension)

LS can extend into multimodal operator context:

- screen OCR context injection,
- real-time voice input,
- offline TTS output,
- optional `QwenOmniWorker` background context capture.

This multimodal loop is an extension of the oversight runtime, not its primary identity.

## Consensus integrity and council governance

LS does not treat repeated text as proof of agreement. Validation and governance layers distinguish between:

- real convergence vs echo-chamber repetition,
- broad support vs direct contradiction,
- base validator winner vs governed winner under review,
- trusted quorum vs trusted veto.

See:
- [`docs/collective-answer-validator.md`](docs/collective-answer-validator.md)
- [`docs/lifetra-validation-adapter.md`](docs/lifetra-validation-adapter.md)

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
    perception/       VisionSubsystem, ScreenCapturer, OCR module
    tts/              Speaker — offline TTS (pyttsx3 + console fallback)
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
| `LS_TTS_ENABLED` | `0` | Speak agent responses aloud via pyttsx3 |

---

## Tests

```bash
# All unit tests (direct — no pytest lthread conflict)
python3 tests/unit/test_stabilization_forces.py
python3 tests/unit/test_system_observer.py
python3 tests/unit/test_new_features.py
python3 tests/unit/test_orientation_force_ladder.py
python3 tests/unit/test_world_poller.py
python3 tests/unit/test_interview_pipeline.py   # multimodal operator pipeline + voice loop

# Qwen Omni + memory store
pytest python/tests/test_qwen_omni_worker.py
pytest python/tests/test_memory_store_locking.py
```

| Test file | Tests | Covers |
|-----------|-------|--------|
| `test_stabilization_forces.py` | 17 | Forces 3–5, stability_bias, trajectory |
| `test_system_observer.py` | 37 | All 6 pathologies, score, trend |
| `test_new_features.py` | 30 | Causal graph, predictive axis, meta-lessons, user profiles, session report |
| `test_orientation_force_ladder.py` | 11 | Forces 1–2, co-activation, propagation |
| `test_world_poller.py` | 8 | WorldPoller git/logs |
| `test_interview_pipeline.py` | 57 | OCR module, VisionSubsystem cache, TTS Speaker, screen-context injection for the operator pipeline |
| `test_qwen_omni_worker.py` | 4 | Multimodal worker fallback + store |

---

## Documentation

| File | Contents |
|------|---------|
| [COGNITIVE_FIELD_COMPLETE.md](COGNITIVE_FIELD_COMPLETE.md) | Full 7-force architecture, learning mechanisms, all APIs |
| [SUBCONSCIOUS_TEMPORAL_LOOP.md](SUBCONSCIOUS_TEMPORAL_LOOP.md) | Subconscious loop + feedback loop diagram |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data flow and system components |
| [docs/architecture/layers.md](docs/architecture/layers.md) | Full 12-layer catalogue |
| [docs/LIMINALQA_TEST_STRATEGY.md](docs/LIMINALQA_TEST_STRATEGY.md) | Strategy for integrating LiminalQAengineer with the current pytest and CI stack |
| [docs/CI_QUALITY_GATES.md](docs/CI_QUALITY_GATES.md) | Active CI quality-gate thresholds, enforcement state, and calibration notes |
| [docs/LIMINALQA_LOCAL_SETUP.md](docs/LIMINALQA_LOCAL_SETUP.md) | Local deployment model for running LiminalQAengineer next to this repository |
| [docs/COUNCIL_CONTRIBUTION_LEDGER_ROADMAP.md](docs/COUNCIL_CONTRIBUTION_LEDGER_ROADMAP.md) | Execution roadmap for unifying council, contribution, reputation, and receiver-resonance tracking |
| [docs/LS_INTEGRATION_ROADMAP.md](docs/LS_INTEGRATION_ROADMAP.md) | Recommended order for integrating adjacent repo subsystems into LS |
| [docs/LS_PHASE1_EXECUTION_PLAN.md](docs/LS_PHASE1_EXECUTION_PLAN.md) | Concrete execution checklist for Phase 1: `LiminalQA + CEL + CouncilContributionLedger` |
| [docs/LS_PHASE2_RELATIONAL_ROADMAP.md](docs/LS_PHASE2_RELATIONAL_ROADMAP.md) | Phase 2 roadmap for moving from reactive oversight into relation-aware orchestration |
| [docs/LS_PHASE2_1_RELATION_MEMORY_EXECUTION_PLAN.md](docs/LS_PHASE2_1_RELATION_MEMORY_EXECUTION_PLAN.md) | Concrete execution checklist for Phase 2.1: relation memory |
| [docs/SAFETY_PROGRAMS_POSITIONING.md](docs/SAFETY_PROGRAMS_POSITIONING.md) | Program-facing framing for fellowships, residencies, grants, and safety-oriented reviews |
| [docs/OPENAI_SAFETY_FELLOWSHIP_POSITIONING.md](docs/OPENAI_SAFETY_FELLOWSHIP_POSITIONING.md) | Fellowship-oriented framing for presenting LS as a safety and oversight runtime |
| [docs/FELLOWSHIP_APPLICATION_BRIEF.md](docs/FELLOWSHIP_APPLICATION_BRIEF.md) | Short application-oriented framing for presenting LS to fellowship reviewers |
| [docs/FELLOWSHIP_APPLICATION_READY.md](docs/FELLOWSHIP_APPLICATION_READY.md) | Single entrypoint doc for what to say, what to show, and what evidence to attach |
| [docs/FELLOWSHIP_DEMO_PATH.md](docs/FELLOWSHIP_DEMO_PATH.md) | Suggested 5–7 minute live demo path for safety- and oversight-oriented review |
| [docs/FELLOWSHIP_REVIEWER_SCRIPT.md](docs/FELLOWSHIP_REVIEWER_SCRIPT.md) | 30-second and 60–90-second spoken script for live fellowship review |
| [docs/FELLOWSHIP_RESEARCH_OUTPUTS.md](docs/FELLOWSHIP_RESEARCH_OUTPUTS.md) | Concrete benchmark, dataset, and note outputs to produce from this repository |
| [docs/FELLOWSHIP_STATEMENT_DRAFT.md](docs/FELLOWSHIP_STATEMENT_DRAFT.md) | Draft statement of purpose for fellowship-style applications |
| [docs/FELLOWSHIP_ONE_PAGER.md](docs/FELLOWSHIP_ONE_PAGER.md) | One-page summary for reviewers, mentors, or intro calls |
| [docs/FELLOWSHIP_QUESTION_BANK.md](docs/FELLOWSHIP_QUESTION_BANK.md) | Reusable short and medium answers for common fellowship application questions |
| [docs/FELLOWSHIP_EVIDENCE_AUDIT.md](docs/FELLOWSHIP_EVIDENCE_AUDIT.md) | Honest gap audit of what evidence already exists and what is still weak |
| [docs/FELLOWSHIP_EVIDENCE_SPRINT.md](docs/FELLOWSHIP_EVIDENCE_SPRINT.md) | 1–2 day sprint plan for strengthening benchmark, dataset, and technical-note evidence |
| [docs/FELLOWSHIP_BENCHMARK_NOTE.md](docs/FELLOWSHIP_BENCHMARK_NOTE.md) | Narrow benchmark note for queue review, replay, and operator-overhead claims |
| [docs/FELLOWSHIP_ATTRIBUTION_NOTE.md](docs/FELLOWSHIP_ATTRIBUTION_NOTE.md) | Short method note for council attribution, receiver resonance, and merit sync |
| [docs/SAFETY_SCORECARD.md](docs/SAFETY_SCORECARD.md) | Risk-state, incident, and operator-guidance view over council cycles |
| [benchmark/README.md](benchmark/README.md) | Benchmark package overview and how to regenerate |
| [benchmark/INTERPRETATION.md](benchmark/INTERPRETATION.md) | What the benchmark numbers justify and do not justify |
| [benchmark/RESULTS.md](benchmark/RESULTS.md) | Generated benchmark snapshot (run `python3 scripts/generate_benchmark_results.py` to refresh) |
| [FINAL_PROJECT_REPORT.md](FINAL_PROJECT_REPORT.md) | Golden Master overview |

---

© 2026 LS Team. Local-first coordination and oversight runtime.

---

<a name="russian"></a>

## Целостность согласования

LS не считает повторяющийся текст доказательством согласия. Слои validation и
governance различают:

- настоящее схождение и echo chamber,
- широкую поддержку и прямое противоречие,
- базового победителя валидатора и governed winner, требующего ревью,
- trusted quorum и trusted veto.

Это важно, потому что многомодельное "согласие" легко подделать. Несколько
агентов могут повторить один и тот же слабый ответ и создать видимость
консенсуса. LS явно фиксирует эту структуру, поднимает coalition risk,
сохраняет support/contradiction edges и помечает раунды, которые нельзя считать
settled consensus без дополнительного review.

См.:
- [`docs/collective-answer-validator.md`](docs/collective-answer-validator.md)
- [`docs/lifetra-validation-adapter.md`](docs/lifetra-validation-adapter.md)

---

# LS — Локальная когнитивная система

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)

LS — это не обёртка над ChatGPT. Это **local-first система согласования и контроля** для человека и моделей: она думает между взаимодействиями, учится на обратной связи и сохраняет решения проверяемыми.

---

## Что это такое простыми словами

Обычный ИИ: вопрос → подумал → ответил → забыл.

LS **живёт между ответами**:
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

## Мультимодальный операторский контур — Глаза + Уши + Голос

LS умеет работать как **hands-free интерфейс для оператора**:

- **Глаза (чтение экрана)** — `VisionSubsystem` снимает скриншот каждые 0.5с и распознаёт текст через OCR (pytesseract или easyocr). Последний текст экрана добавляется в каждый LLM-запрос как системное сообщение — агент видит текущий операторский контекст без ручного копирования.
- **Уши (голосовой ввод)** — `faster-whisper` + PyAudio слушают микрофон и транскрибируют речь в текст в реальном времени. Транскрипт идёт в агент как сообщение пользователя.
- **Голос (TTS)** — `Speaker` (pyttsx3, полностью оффлайн) читает ответ агента вслух, чтобы оператор мог оставаться в потоке без постоянного взгляда на экран.

```
┌──────────┐   OCR     ┌──────────────────┐  system msg   ┌──────────┐
│  Экран   │ ────────► │  VisionSubsystem  │ ────────────► │          │
└──────────┘           └──────────────────┘               │  Agent   │ ──► TTS ──► наушник
                                                           │  Loop    │
┌──────────┐  Whisper  ┌───────────────┐  user msg        │          │
│   Мик    │ ────────► │  AudioInput   │ ───────────────► │          │
└──────────┘           └───────────────┘                  └──────────┘
```

### Активация

```bash
pip install pyttsx3               # TTS (оффлайн)
pip install pytesseract           # OCR (или: pip install easyocr)
# для pytesseract: установи бинарник tesseract для своей ОС

export LS_TTS_ENABLED=1           # включить голосовой вывод
python apps/console/main.py
```

---

## Архитектура

```
AgentLoop
  ├── Screen OCR (VisionSubsystem) ─►
  ├── Mic / Whisper                ─►  TemporalGraph
  ├── Subconscious loop (20s)      ─►  (узлы + рёбра)
  ├── WorldPoller (git/logs)       ─►
  ├── Quality feedback             ─►
  └── Auto feedback proxy          ─►
                                        │
                              Coordinator.decide()
                              7 сил за цикл
                                        │
                              OrientationCenter ◄──► сигнал обратно
                                        │
                        sleep → session_report → lesson:session:*
                                        │
                              TTS Speaker ◄── ответ
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

### Мультимодальный голосовой контур (опционально)

```bash
pip install pyttsx3 pytesseract     # или easyocr вместо pytesseract
export LS_TTS_ENABLED=1
python apps/console/main.py
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

| | Обычный агент | LS |
|--|---------------|----------|
| Между сообщениями | Простаивает | Подсознание работает |
| Обучение | По запросу | Непрерывно (4 источника) |
| Память | Плоская история | Граф с резонансом и распадом |
| Самоконтроль | Нет | Наблюдатель корректирует патологии |
| Модель пользователя | Нет | Профиль + предсказание режима |
| Отказ | Тихий дрейф | Обнаруживается и исправляется |
| Вход | Только текст | Текст + голос + экран (OCR) |
| Выход | Только текст | Текст + голос (TTS) |

---

© 2026 LS Team. Strictly Local. Strictly Cognitive.
