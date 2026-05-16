# LS — Local-First Coordination and Oversight Runtime

[English](#english) | [Русский](#russian)

---

<a name="english"></a>

# LS — Local-First Coordination and Oversight Runtime

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Council Safety Gate](https://github.com/safal207/LS/actions/workflows/council_safety.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/council_safety.yml)
[![Landing Pages](https://github.com/safal207/LS/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/pages.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](LICENSE)
[![Rust Powered](https://img.shields.io/badge/Rust-Inside-orange.svg)](#core-architecture-summary)

Live site: [GitHub Pages](https://safal207.github.io/LS/)
Community: [Roadmap](ROADMAP.md) · [Task board](docs/COMMUNITY_TASKS.md) · [Contributing](CONTRIBUTING.md)
Reviewer ecosystem: [Ecosystem Reviewer Index](docs/ECOSYSTEM_REVIEWER_INDEX.md)

**LS is a local-first coordination and oversight runtime for human-plus-model systems.**
It records council cycles (structured multi-model decision rounds), tracks contribution and receiver resonance (a signal of how cleanly outcomes were accepted), exposes approval-safe operator workflows, and produces replayable artifacts for evaluation and governance.
Instead of treating model output as a black box, LS turns decision cycles into measurable, reviewable, and improvable runtime artifacts.

It is also a **personal AI operating layer**: a system that lets any model or agent pass through your memory, quality, coordination, and review logic before it reaches you.

LS also supports a **Personal Cognitive Garden** direction: AI sessions should compound into a human-owned, goal-directed graph of goals, skills, decisions, constraints, evidence, reflections, and growth paths. Agents may help cultivate that graph, but the person owns it and governance decides what becomes durable state.

---

## Personal AI Operating Layer

LS can be used as a layer *above* agents, not just as another agent:

- connect different agents while keeping one center of memory, tone, and quality;
- shape, repair, hold, or escalate raw outputs before they become action;
- preserve personal context across models, tools, and sessions;
- use coordination, relational, and harmonic diagnostics to catch weak or misaligned output early.

Short version:

> do not use agents as-is; run them through your own system so they work in your logic, your rhythm, and your quality.

Personal growth direction:

> Every AI session should compound into human development.

Run the local Personal Cognitive Garden demo:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py
python3 scripts/run_personal_cognitive_garden_demo.py --json
```

Run the Codex plugin demo:

- [`docs/CODEX_PLUGIN_DEMO.md`](docs/CODEX_PLUGIN_DEMO.md)

Safety boundary:

> LS must grow human-owned skill capital without becoming a corporate surveillance layer.

See the red-team scenario:

- [`docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md`](docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md)

See:
- [`ROADMAP.md`](ROADMAP.md)
- [`docs/COMMUNITY_TASKS.md`](docs/COMMUNITY_TASKS.md)
- [`docs/GITHUB_PAGES_SETUP.md`](docs/GITHUB_PAGES_SETUP.md)
- [`docs/PERSONAL_GROWTH_ENTRY.md`](docs/PERSONAL_GROWTH_ENTRY.md)
- [`docs/LS_PERSONAL_COGNITIVE_GARDEN.md`](docs/LS_PERSONAL_COGNITIVE_GARDEN.md)
- [`docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md`](docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md)
- [`docs/positioning/personal-ai-operating-layer.md`](docs/positioning/personal-ai-operating-layer.md)
- [`docs/personal-agent-gateway-runtime.md`](docs/personal-agent-gateway-runtime.md)
- [`docs/harmonic-state-model-mvp.md`](docs/harmonic-state-model-mvp.md)

Current runtime contract now exposes:

- `raw_agent_output`
- `final_output`
- `personal_agent_gateway`
- `gateway_mode`
- `gateway_reason`
- `operator_identity_governance`
- `operator_profile_write_decision`
- `action_evidence_gate`

### Before vs now, in simple terms

Before, LS mostly acted like a smart helper at the door:

```text
Agent: here is my answer.
LS: is the answer clear, safe, warm, and aligned enough to show?
```

The main question was:

```text
How should this answer reach the human?
```

Now LS also acts like a trusted checkpoint with a decision log:

```text
Agent: I want to write memory, change profile state, or take an action.
LS: did the operator confirm it, is there source evidence, is the scope allowed,
and can we prove later why this was allowed, held, or rejected?
```

The new question is:

```text
Can this agent output become memory, profile state, or action at all?
```

Example:

```text
Agent: write "the user always wants short answers" into the profile.

LS checks:
1. Did the user explicitly confirm this profile write?
2. Is there source evidence?
3. Is the agent deciding for the user?
4. Can the decision be replayed and verified later?

Decision:
hold
stop_reason:
missing_operator_confirmation
```

In plain language: LS used to help agents say things better. Now it also checks whether an agent is allowed to turn words into memory, profile, or action.

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
2. [`docs/ECOSYSTEM_REVIEWER_INDEX.md`](docs/ECOSYSTEM_REVIEWER_INDEX.md)
3. [`docs/SAFETY_PROGRAMS_POSITIONING.md`](docs/SAFETY_PROGRAMS_POSITIONING.md)
4. [`docs/FELLOWSHIP_APPLICATION_READY.md`](docs/FELLOWSHIP_APPLICATION_READY.md)
5. [`docs/FELLOWSHIP_DEMO_PATH.md`](docs/FELLOWSHIP_DEMO_PATH.md)
6. [`benchmark/README.md`](benchmark/README.md)
7. [`benchmark/RESULTS.md`](benchmark/RESULTS.md)

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

# Text chat through the LS personal agent gateway
PYTHONPATH=python python -m ls.agent_shell.cli chat

# Web/mobile gateway for phones and external agents
PYTHONPATH=python python -m ls.agent_shell.cli web-gateway --host 0.0.0.0 --port 8787

# Custom GPT Action schema
# https://your-public-ls-url/gpt/actions/openapi.json

# One-shot chat message
PYTHONPATH=python python -m ls.agent_shell.cli chat "Explain what LS can do for agents."

# Multi-agent demo (3 coordinated agents)
python -m apps.multi_agent_demo

# Personal Cognitive Garden demo
python3 scripts/run_personal_cognitive_garden_demo.py
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
| [docs/ECOSYSTEM_REVIEWER_INDEX.md](docs/ECOSYSTEM_REVIEWER_INDEX.md) | Top-level reviewer index linking LS to ProofPath, PythiaLabs, CML, and LTP |
| [docs/PERSONAL_GROWTH_ENTRY.md](docs/PERSONAL_GROWTH_ENTRY.md) | Short entry point for the Personal Cognitive Garden and human-development positioning |
| [docs/LS_PERSONAL_COGNITIVE_GARDEN.md](docs/LS_PERSONAL_COGNITIVE_GARDEN.md) | Thesis for LS as a human-owned, goal-directed cognitive garden cultivated by agents |
| [docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md](docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md) | Local runner instructions for replaying the Personal Cognitive Garden demo flow |
| [docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md](docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md) | Red-team scenario for blocking employer surveillance misuse of a private cognitive garden |
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

# LS — Local-first координационный и oversight runtime

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Council Safety Gate](https://github.com/safal207/LS/actions/workflows/council_safety.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/council_safety.yml)
[![Landing Pages](https://github.com/safal207/LS/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/pages.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#быстрый-старт)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)

Сайт: [GitHub Pages](https://safal207.github.io/LS/)
Сообщество: [дорожная карта](ROADMAP.md) · [задачи](docs/COMMUNITY_TASKS.md) · [как помочь](CONTRIBUTING.md)
Экосистема для ревьюеров: [Ecosystem Reviewer Index](docs/ECOSYSTEM_REVIEWER_INDEX.md)

**LS — это local-first runtime для координации и oversight в системах человек + модели.**
Он фиксирует council cycles (структурированные раунды многомодельных решений), отслеживает вклад и receiver resonance (насколько результат был принят получателем без трения), поддерживает approval-safe операторские потоки и выпускает replayable-артефакты для оценки и governance.

LS также поддерживает направление **Personal Cognitive Garden**: AI-сессии должны накапливаться в принадлежащий человеку целевой граф развития — цели, навыки, решения, ограничения, доказательства, рефлексии и следующие шаги. Агенты помогают ухаживать за этим графом, но человек владеет им, а governance решает, что становится долговременным состоянием.

Быстрое демо Personal Cognitive Garden:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py
```

Safety boundary: LS должен развивать принадлежащий человеку skill capital, не превращаясь в corporate surveillance layer.

См. red-team сценарий: [`docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md`](docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md)

---

## Зачем существует LS

Большинство AI-систем дают ответ, но не сохраняют структуру, пригодную для проверки:

- кто реально участвовал,
- по какому маршруту пришли к решению,
- что именно было принято,
- где был операторский контроль и approval,
- как оценить качество и повторяемость цикла.

LS нужен, чтобы превращать model-assisted координацию в измеряемые и проверяемые runtime-артефакты.

## Что это на практике

LS — это операторский runtime-слой вокруг decision cycle:

- запускает council-раунды вместо одной «чёрной коробки»;
- сохраняет структурированные артефакты для replay и post-hoc review;
- учитывает contribution / merit / resonance сигналы;
- поддерживает approval-safe вмешательство оператора;
- выводит quality-gated результаты, пригодные для benchmark и evidence-пакета.

## Поверхность доказательств (Evidence surface)

В репозитории уже есть проверяемый слой поведения:

- replayable traces для инспекции задач и council-циклов;
- council result artifacts с полями для анализа;
- contribution / merit / resonance сигналы (`CouncilContributionLedger`, `CEL`);
- quality gates и машиночитаемые отчёты (`LiminalQA`, CI-пороги);
- benchmark-снимки в [`benchmark/`](benchmark/);
- `Council Safety Gate` в CI.

## Safety / oversight релевантность

LS позиционируется как инфраструктура oversight, а не как «удобный чат-ассистент».

Ключевые safety-поверхности:

- измеримый вклад участников и принятие результата,
- replay и инспекция council-циклов,
- approval-safe операторские workflows,
- quality-gated артефакты для оценки и governance.

Основной позиционирующий документ:
- [`docs/SAFETY_PROGRAMS_POSITIONING.md`](docs/SAFETY_PROGRAMS_POSITIONING.md)

## Что ревьюеру важно понять сначала

1. Это проект про oversight, а не про удобный prompting.
2. Здесь есть инженерные артефакты, а не только идеи.
3. LS уже выдаёт измеримые traces, scorecards и evaluation outputs.
4. Из текущего пакета реалистично собрать benchmark/dataset/demo артефакт.

## Лучший путь для ревьюера

1. [README.md](README.md)
2. [`docs/ECOSYSTEM_REVIEWER_INDEX.md`](docs/ECOSYSTEM_REVIEWER_INDEX.md)
3. [`docs/SAFETY_PROGRAMS_POSITIONING.md`](docs/SAFETY_PROGRAMS_POSITIONING.md)
4. [`docs/FELLOWSHIP_APPLICATION_READY.md`](docs/FELLOWSHIP_APPLICATION_READY.md)
5. [`docs/FELLOWSHIP_DEMO_PATH.md`](docs/FELLOWSHIP_DEMO_PATH.md)
6. [`benchmark/README.md`](benchmark/README.md)
7. [`benchmark/RESULTS.md`](benchmark/RESULTS.md)

## Базовая архитектура (кратко)

```
AgentLoop
  ├── Subconscious / WorldPoller / Feedback
  ├── TemporalGraph + Coordinator
  ├── Council artifacts / traces / score updates
  └── Operator review and approval path
```

## Когнитивные механизмы (внутренний слой)

Когнитивная архитектура в LS сохранена, но является поддерживающим механизмом runtime oversight:

- 7 forces (`Coordinator.decide()`),
- само-мониторинг (`SystemObserver`),
- подсознательный цикл + память + профили пользователя.

См. подробнее:
- [COGNITIVE_FIELD_COMPLETE.md](COGNITIVE_FIELD_COMPLETE.md)
- [SUBCONSCIOUS_TEMPORAL_LOOP.md](SUBCONSCIOUS_TEMPORAL_LOOP.md)

## Мультимодальный операторский контур (вторичный слой)

LS поддерживает расширение до multimodal operator loop:

- OCR-контекст экрана,
- голосовой ввод,
- офлайн TTS,
- `QwenOmniWorker` как опциональный фоновый воркер.

Это полезное расширение, но не основной публичный identity LS.

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

### Голосовой контур (опционально)

```bash
pip install pyttsx3 pytesseract     # или easyocr вместо pytesseract
export LS_TTS_ENABLED=1
python apps/console/main.py
```

---

© 2026 LS Team. Local-first coordination and oversight runtime.
