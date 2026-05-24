# LS — Cooperative Precision Layer for AI Co-work

[English](#english) | [Русский](#russian)

---

<a name="english"></a>

# LS — Cooperative Precision Layer for AI Co-work

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Council Safety Gate](https://github.com/safal207/LS/actions/workflows/council_safety.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/council_safety.yml)
[![Cognitive Trail Contract](https://github.com/safal207/LS/actions/workflows/cognitive_trail_contract.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/cognitive_trail_contract.yml)
[![Landing Pages](https://github.com/safal207/LS/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/pages.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](LICENSE)
[![Rust Powered](https://img.shields.io/badge/Rust-Inside-orange.svg)](#core-architecture-summary)

Live site: [GitHub Pages](https://safal207.github.io/LS/)
Community: [Roadmap](ROADMAP.md) · [Task board](docs/COMMUNITY_TASKS.md) · [Cognitive Trail tasks](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) · [Contributing](CONTRIBUTING.md)
Reviewer ecosystem: [Ecosystem Reviewer Index](docs/ECOSYSTEM_REVIEWER_INDEX.md)
Cooperative precision: [Evidence Snapshot](docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md) · [Reviewer Quickstart](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md) · [Contributor Tasks](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) · [Benchmark Note](docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md) · [Metrics](docs/COOPERATIVE_PRECISION_METRICS.md) · [Precision Stack](docs/COOPERATIVE_PRECISION_STACK.md) · [Network Precision Gain](docs/NETWORK_PRECISION_GAIN.md) · [Stability Probe](docs/COOPERATIVE_PRECISION_METRICS.md#nash-style-route-stability) · [Stability Sample](examples/route-stability/nash_route_stability_sample.json) · [Stability Contract](docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md) · [Stability Evidence Map](docs/ROUTE_STABILITY_EVIDENCE_MAP.md) · [Roadmap](docs/COOPERATIVE_PRECISION_ROADMAP.md) · [Cognitive Trail Network](docs/COGNITIVE_TRAIL_NETWORK.md) · [PR Role Market Benchmark](docs/PR_ROLE_MARKET_BENCHMARK.md)
Contributor calls: [Network Precision Contributor Call](docs/NETWORK_PRECISION_CONTRIBUTOR_CALL.md) · [Route Stability Contributor Runs](docs/ROUTE_STABILITY_CONTRIBUTOR_RUNS.md) · [Issue #563 contributor matrix](https://github.com/safal207/LS/issues/563)
Meta-interaction: [Depth Economy Layer](docs/DEPTH_ECONOMY_LAYER.md) · [Amygdala Layer Map](docs/AMYGDALA_LAYER_MAP.md) · [Model Roster Depth Probe](docs/MODEL_ROSTER_DEPTH_PROBE.md)
MCP bridge: [LS Trail MCP Server v0.2](docs/LS_TRAIL_MCP_SERVER.md)
Positioning: [Project Positioning](docs/PROJECT_POSITIONING.md)
New here? Start with: [Why Star LS](docs/WHY_STAR_LS.md) · [2-minute route-stability demo](#2-minute-route-stability-demo) · [Network precision contributor call](docs/NETWORK_PRECISION_CONTRIBUTOR_CALL.md) · [Contributor matrix](https://github.com/safal207/LS/issues/563)

**LS is a local-first cooperative precision layer for human-plus-model work.**
It does not make models magically smarter. It makes repeated cooperation more
precise by checking continuity, evidence, consent, routes, and contributions
before outputs become actions, memory, or reputation.

## First 10 seconds

LS is for people who use AI heavily and do not want useful sessions to vanish
inside chat history.

It turns an AI session into a reviewed update: a goal, skill, decision,
evidence item, or growth path. Nothing becomes durable personal memory until a
human accepts it.

The core loop:

```text
task -> route -> evidence -> contribution -> decision -> reusable artifact
```

First wedge: **AI Code Review / PR Review Trail Network**. A real git diff can
be routed through draft review, risk critique, evidence verification, and final
summary, then saved as a reusable trail artifact.

LS also contains a **Personal Cognitive Garden** direction: useful AI sessions
can become human-owned development memory, but only with evidence and human
review. The system must grow skill capital without becoming surveillance.

### 2-minute route-stability demo

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
python scripts/run_nash_route_stability_demo.py --json
```

This checks the current route-stability evidence chain:

```text
schema
-> checked-in sample
-> negative fixtures
-> deterministic probe
-> regression test
-> explicit non-claims
```

Want to help? Try the [network precision contributor call](docs/NETWORK_PRECISION_CONTRIBUTOR_CALL.md): run the same bounded probe on your OS, model runtime, and hardware. You can also join the [route-stability contributor matrix](https://github.com/safal207/LS/issues/563).

Run the PR-review trail demo:

```bash
python3 scripts/run_pr_review_trail_demo.py
```

Build a real PR-review trail artifact from the latest git commit:

```bash
python3 scripts/run_pr_review_trail_artifact.py
```

Build a free-only PR-review route packet for Codex, local models, or human review:

```bash
python3 scripts/run_free_pr_review_route.py
```

Run the Cooperative Role Market demo:

```bash
python3 scripts/run_role_market_demo.py
```

Score cooperative roles over a real PR-style git diff:

```bash
python3 scripts/run_pr_role_market_demo.py
python3 scripts/run_pr_role_market_demo.py --role-outputs docs/examples/pr_role_outputs.sample.json
python3 scripts/run_pr_role_market_batch.py --last 10
```

Run the Nash-style route stability probe:

```bash
python3 scripts/run_nash_route_stability_demo.py
```

Checked-in stability sample:

```text
examples/route-stability/nash_route_stability_sample.json
```

Boundary: this is a route-stability proxy, not a formal proof of Nash equilibrium.

Reviewer quickstart for Cognitive Trail validation:

```bash
python3 scripts/validate_cognitive_trail_runs.py
python3 scripts/generate_pr_review_trail_run.py --last 10 --validate
```

See: [`docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md`](docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md)
Reviewer quickstart: [`docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md`](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md)
Benchmark note: [`docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md`](docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md)
Cooperative metrics: [`docs/COOPERATIVE_PRECISION_METRICS.md`](docs/COOPERATIVE_PRECISION_METRICS.md)
Stability sample: [`examples/route-stability/nash_route_stability_sample.json`](examples/route-stability/nash_route_stability_sample.json)
Stability contract: [`docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md`](docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md)
Stability evidence map: [`docs/ROUTE_STABILITY_EVIDENCE_MAP.md`](docs/ROUTE_STABILITY_EVIDENCE_MAP.md)
Contributor tasks: [`docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md`](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md)

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

New contributors can use the focused PCG quick start:

- [`docs/PERSONAL_COGNITIVE_GARDEN_QUICK_START.md`](docs/PERSONAL_COGNITIVE_GARDEN_QUICK_START.md)

See a compact before/after example:

- [`docs/PERSONAL_COGNITIVE_GARDEN_GATEWAY_BEFORE_AFTER.md`](docs/PERSONAL_COGNITIVE_GARDEN_GATEWAY_BEFORE_AFTER.md)
- [`examples/personal_cognitive_garden/gateway_to_garden_before_after.json`](examples/personal_cognitive_garden/gateway_to_garden_before_after.json)

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
- [`docs/COGNITIVE_TRAIL_NETWORK.md`](docs/COGNITIVE_TRAIL_NETWORK.md)
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
- **Cognitive trail route memory** (`TrailUpdater`, route rewards, route pheromone weights)
- **Nash-style route stability proxy** for testing whether a cooperative route beats single-route, ablation, and bad-ordering counterfactuals
- **Checked-in Nash-style stability sample** (`examples/route-stability/nash_route_stability_sample.json`)
- **Route stability sample contract** (`docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md`) for schema, negative fixture, deterministic probe, CI summary, artifact boundary, and non-claims
- **Route stability evidence map** (`docs/ROUTE_STABILITY_EVIDENCE_MAP.md`) for reviewer navigation across the sample, schema, negative fixture, test, CI surface, artifact, and failure modes
- **Quality gates and machine-readable reports** (`LiminalQA`, CI thresholds)
- **Benchmark snapshots** and interpretation notes under [`benchmark/`](benchmark/)
- **Council Safety Gate in CI** for risk-aware review enforcement

If you are evaluating this repo, start by checking these artifacts before reading internal mechanism details.

## Safety and oversight relevance

LS is positioned as cooperative precision infrastructure, not convenience
prompting UX. The safety claim is narrow: repeated AI co-work should become more
precise because routes, evidence, consent, and contributions are visible.

Safety-relevant surfaces include:

- measurable model participation and adoption,
- replayable cycle traces and post-hoc inspection,
- approval-safe operator workflows,
- quality-gated outputs and CI enforcement,
- packaging for benchmark/dataset/demo artifacts.

Primary positioning docs:

- [`docs/PROJECT_POSITIONING.md`](docs/PROJECT_POSITIONING.md)
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
python3 tests/unit/test_operator_pipeline_flow.py   # multimodal operator pipeline + voice loop

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
| `test_operator_pipeline_flow.py` | 57 | OCR module, VisionSubsystem cache, TTS Speaker, screen-context injection for the operator pipeline |
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
| [docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md](docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md) | One-page reviewer snapshot for Cognitive Trail evidence, commands, CI artifacts, limitations, and non-claims |
| [docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md) | Two-minute reviewer path for validating Cognitive Trail contracts and generated PR-review trail runs |
| [docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) | Focused contributor tasks for hardening Cognitive Trail fixtures, validator, reporting, CI artifacts, and benchmark coverage |
| [docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md](docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md) | Short benchmark note for the Cognitive Trail PR-review result, metrics, reproduction path, and non-claims |
| [docs/COOPERATIVE_PRECISION_METRICS.md](docs/COOPERATIVE_PRECISION_METRICS.md) | Cooperative precision metrics, including the Nash-style route stability proxy and its interpretation boundary |
| [docs/COOPERATIVE_PRECISION_STACK.md](docs/COOPERATIVE_PRECISION_STACK.md) | Six-path stack map for immutable traces, adaptive memory, evidence gates, route scoring, reflection, and human boundary |
| [docs/NETWORK_PRECISION_GAIN.md](docs/NETWORK_PRECISION_GAIN.md) | Deterministic proxy for measuring how much precision the cooperative stack adds over a single answer |
| [docs/MODEL_ROSTER_DEPTH_PROBE.md](docs/MODEL_ROSTER_DEPTH_PROBE.md) | Probe for checking which LS model actors exist in the roster and which are live for Depth Economy routing |
| [docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md](docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md) | Reviewer-facing contract for the route-stability sample schema, checked-in sample, deterministic probe, regression test, CI artifact, and non-claims |
| [docs/ROUTE_STABILITY_EVIDENCE_MAP.md](docs/ROUTE_STABILITY_EVIDENCE_MAP.md) | Reviewer-facing evidence map showing which route-stability file proves what, how to verify it, and which failures stale the sample |
| [examples/route-stability/nash_route_stability_sample.json](examples/route-stability/nash_route_stability_sample.json) | Checked-in Nash-style route stability sample pinned by `python/tests/test_nash_route_stability.py` |
| [docs/PERSONAL_GROWTH_ENTRY.md](docs/PERSONAL_GROWTH_ENTRY.md) | Short entry point for the Personal Cognitive Garden and human-development positioning |
| [docs/LS_PERSONAL_COGNITIVE_GARDEN.md](docs/LS_PERSONAL_COGNITIVE_GARDEN.md) | Thesis for LS as a human-owned, goal-directed cognitive garden cultivated by agents |
| [docs/PERSONAL_COGNITIVE_GARDEN_QUICK_START.md](docs/PERSONAL_COGNITIVE_GARDEN_QUICK_START.md) | Minimal local quick start for the Personal Cognitive Garden demo runner |
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

© 2026 LS Team. Cooperative precision layer for AI co-work.

---

<a name="russian"></a>

# LS — слой точности кооперации для работы человека и ИИ

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Council Safety Gate](https://github.com/safal207/LS/actions/workflows/council_safety.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/council_safety.yml)
[![Cognitive Trail Contract](https://github.com/safal207/LS/actions/workflows/cognitive_trail_contract.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/cognitive_trail_contract.yml)
[![Landing Pages](https://github.com/safal207/LS/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/pages.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#быстрый-старт)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)

Сайт: [GitHub Pages](https://safal207.github.io/LS/)
Сообщество: [дорожная карта](ROADMAP.md) · [задачи](docs/COMMUNITY_TASKS.md) · [задачи Cognitive Trail](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) · [как помочь](CONTRIBUTING.md)
Экосистема для ревьюеров: [Ecosystem Reviewer Index](docs/ECOSYSTEM_REVIEWER_INDEX.md)
Точность кооперации: [Evidence Snapshot](docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md) · [Reviewer Quickstart](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md) · [Contributor Tasks](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) · [Benchmark Note](docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md) · [Metrics](docs/COOPERATIVE_PRECISION_METRICS.md) · [Precision Stack](docs/COOPERATIVE_PRECISION_STACK.md) · [Network Precision Gain](docs/NETWORK_PRECISION_GAIN.md) · [Stability Probe](docs/COOPERATIVE_PRECISION_METRICS.md#nash-style-route-stability) · [Stability Sample](examples/route-stability/nash_route_stability_sample.json) · [Stability Contract](docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md) · [Stability Evidence Map](docs/ROUTE_STABILITY_EVIDENCE_MAP.md) · [Cognitive Trail Network](docs/COGNITIVE_TRAIL_NETWORK.md) · [PR Role Market Benchmark](docs/PR_ROLE_MARKET_BENCHMARK.md)
MCP-мост: [LS Trail MCP Server v0.2](docs/LS_TRAIL_MCP_SERVER.md)
Позиционирование: [Project Positioning](docs/PROJECT_POSITIONING.md)
Впервые здесь? Начните с: [Why Star LS](docs/WHY_STAR_LS.md) · [2-minute route-stability demo](#2-minute-route-stability-demo) · [Contributor matrix](https://github.com/safal207/LS/issues/563)

**LS — это local-first слой точности кооперации для систем человек + модели.**
Он не делает модели магически “умнее”. Он делает повторяющуюся совместную работу
точнее: проверяет контекст, доказательства, согласие, маршрут и вклад участников
до того, как ответ станет действием, памятью или репутацией.

## Первые 10 секунд

LS нужен человеку, который много работает с ИИ и не хочет, чтобы полезные
сессии исчезали в истории чата.

LS превращает сессию с ИИ в проверенное обновление: цель, навык, решение,
доказательство или направление роста. Ничего не становится личной памятью,
пока человек сам это не примет.

Короткая формула:

```text
задача -> маршрут -> доказательства -> вклад -> решение -> reusable artifact
```

Первый прикладной вход — **AI Code Review / PR Review Trail Network**: реальный
git diff проходит через маршрут проверки, получает сигналы риска, route reward и
сохраняется как проверяемый артефакт для следующей похожей задачи.

Быстрый запуск PR-review артефакта:

```bash
python3 scripts/run_pr_review_trail_artifact.py
```

Бесплатный маршрут без платных model API:

```bash
python3 scripts/run_free_pr_review_route.py
```

Демо рынка ролей:

```bash
python3 scripts/run_role_market_demo.py
```

Оценка ролей на реальном PR/diff:

```bash
python3 scripts/run_pr_role_market_demo.py
python3 scripts/run_pr_role_market_demo.py --role-outputs docs/examples/pr_role_outputs.sample.json
python3 scripts/run_pr_role_market_batch.py --last 10
```

Проверка Nash-style route stability:

```bash
python3 scripts/run_nash_route_stability_demo.py
```

Checked-in stability sample:

```text
examples/route-stability/nash_route_stability_sample.json
```

Граница: это proxy устойчивости маршрута, а не формальное доказательство равновесия Нэша.

Проверка Cognitive Trail для ревьюера:

```bash
python3 scripts/validate_cognitive_trail_runs.py
python3 scripts/generate_pr_review_trail_run.py --last 10 --validate
```

См.: [`docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md`](docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md)
Reviewer quickstart: [`docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md`](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md)
Benchmark note: [`docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md`](docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md)
Cooperative metrics: [`docs/COOPERATIVE_PRECISION_METRICS.md`](docs/COOPERATIVE_PRECISION_METRICS.md)
Stability sample: [`examples/route-stability/nash_route_stability_sample.json`](examples/route-stability/nash_route_stability_sample.json)
Stability contract: [`docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md`](docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md)
Stability evidence map: [`docs/ROUTE_STABILITY_EVIDENCE_MAP.md`](docs/ROUTE_STABILITY_EVIDENCE_MAP.md)
Contributor tasks: [`docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md`](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md)

LS также поддерживает направление **Personal Cognitive Garden**: полезные
AI-сессии могут становиться принадлежащей человеку памятью развития, но только с
доказательствами и ручной проверкой. Система должна развивать skill capital, не
превращаясь в надзор.

Быстрое демо Personal Cognitive Garden:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py
```

Короткий пример "до/после" от сырого ответа агента до решения LS:

- [`docs/PERSONAL_COGNITIVE_GARDEN_GATEWAY_BEFORE_AFTER.md`](docs/PERSONAL_COGNITIVE_GARDEN_GATEWAY_BEFORE_AFTER.md)
- [`examples/personal_cognitive_garden/gateway_to_garden_before_after.json`](examples/personal_cognitive_garden/gateway_to_garden_before_after.json)

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
- Nash-style route stability proxy для проверки, выигрывает ли полный кооперативный маршрут у single-route, ablation и плохого порядка;
- checked-in Nash-style stability sample (`examples/route-stability/nash_route_stability_sample.json`);
- contract для route-stability sample (`docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md`): schema, negative fixture, deterministic probe, CI summary, artifact boundary и non-claims;
- evidence map для route-stability sample (`docs/ROUTE_STABILITY_EVIDENCE_MAP.md`): reviewer navigation по sample, schema, negative fixture, test, CI surface, artifact и failure modes;
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

© 2026 LS Team. Cooperative precision layer for AI co-work.
