# LS — Cooperative Precision Layer for AI Co-work

[English](#english) | [Русский](#russian)

---

<a name="english"></a>

# LS — Cooperative Precision Layer for AI Co-work

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Council Safety Gate](https://github.com/safal207/LS/actions/workflows/council_safety.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/council_safety.yml)
[![Cognitive Trail Contract](https://github.com/safal207/LS/actions/workflows/cognitive_trail_contract.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/cognitive_trail_contract.yml)
[![Trusted Runtime Contract](https://github.com/safal207/LS/actions/workflows/trusted_runtime_contract.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/trusted_runtime_contract.yml)
[![Landing Pages](https://github.com/safal207/LS/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/pages.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#quick-start)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](LICENSE)
[![Rust Powered](https://img.shields.io/badge/Rust-Inside-orange.svg)](#core-architecture-summary)

Live site: [GitHub Pages](https://safal207.github.io/LS/)
Community: [Roadmap](ROADMAP.md) · [Task board](docs/COMMUNITY_TASKS.md) · [Cognitive Trail tasks](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) · [Contributing](CONTRIBUTING.md)
Reviewer ecosystem: [Ecosystem Reviewer Index](docs/ECOSYSTEM_REVIEWER_INDEX.md)
Cooperative precision: [Evidence Snapshot](docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md) · [Reviewer Quickstart](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md) · [Contributor Tasks](docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md) · [Benchmark Note](docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md) · [Metrics](docs/COOPERATIVE_PRECISION_METRICS.md) · [Precision Stack](docs/COOPERATIVE_PRECISION_STACK.md) · [Network Precision Gain](docs/NETWORK_PRECISION_GAIN.md) · [Stability Probe](docs/COOPERATIVE_PRECISION_METRICS.md#nash-style-route-stability) · [Stability Sample](examples/route-stability/nash_route_stability_sample.json) · [Stability Contract](docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md) · [Stability Evidence Map](docs/ROUTE_STABILITY_EVIDENCE_MAP.md) · [Roadmap](docs/COOPERATIVE_PRECISION_ROADMAP.md) · [Cognitive Trail Network](docs/COGNITIVE_TRAIL_NETWORK.md) · [PR Role Market Benchmark](docs/PR_ROLE_MARKET_BENCHMARK.md)
Contributor calls: [Network Precision Contributor Call](docs/NETWORK_PRECISION_CONTRIBUTOR_CALL.md) · [IDE Testing Entrypoints](docs/IDE_TESTING_ENTRYPOINTS.md) · [Route Stability Contributor Runs](docs/ROUTE_STABILITY_CONTRIBUTOR_RUNS.md) · [Issue #563 contributor matrix](https://github.com/safal207/LS/issues/563)
Meta-interaction: [Depth Economy Layer](docs/DEPTH_ECONOMY_LAYER.md) · [Amygdala Layer Map](docs/AMYGDALA_LAYER_MAP.md) · [Model Roster Depth Probe](docs/MODEL_ROSTER_DEPTH_PROBE.md)
MCP bridge: [LS Trail MCP Server v0.2](docs/LS_TRAIL_MCP_SERVER.md)
Trusted Runtime: [Contract Architecture](docs/trusted-runtime/ARCHITECTURE.md) · [Epic #599](https://github.com/safal207/LS/issues/599) · [Contributor entry #601](https://github.com/safal207/LS/issues/601)
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

### Skills vs LS Network

Skills are useful instructions for one agent. LS Network is the accumulated
experience of routes: memory, metrics, evidence, and contributor signals.

| Skills | LS Network |
| --- | --- |
| static instruction | accumulated experience |
| helps one agent act | helps the network choose a route |
| says how to do the task | measures what actually worked |
| usually does not know who contributed | scores role and actor contribution |
| may skip result verification | requires evidence, trace, and route score |
| lives inside an agent | connects Codex, OpenCode, Cursor, and models through MCP |

Short version:

```text
skill = instruction
LS Network = verified route experience
```

First wedge: **AI Code Review / PR Review Trail Network**. A real git diff can
be routed through draft review, risk critique, evidence verification, and final
summary, then saved as a reusable trail artifact.

LS also contains a **Personal Cognitive Garden** direction: useful AI sessions
can become human-owned development memory, but only with evidence and human
review. The system must grow skill capital without becoming surveillance.

### Trusted Cooperative Runtime foundation

The Trusted Runtime contract layer defines provider-neutral workflow, route,
causal-trail, evidence, authorization, replay, and reusable-artifact records.
It treats model output as a proposal rather than execution permission and keeps
external ecosystem modules behind explicit adapter boundaries.

Run the focused contract tests:

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_*.py
```

See [`docs/trusted-runtime/ARCHITECTURE.md`](docs/trusted-runtime/ARCHITECTURE.md).

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

Fastest IDE path: in VS Code or Cursor, run **Terminal -> Run Task... -> LS: Prepare Contributor Report** and paste the generated Markdown report into the contributor issue. In OpenCode, run `/ls-precision-report your-github-handle` from the repository.

Run the PR-review trail demo:

```bash
python3 scripts/run_pr_review_trail_demo.py
```
## PR review trail demo screenshot

Example output from the PR review trail demo command.

![PR review trail demo](./assets/pr_review_demo.png)

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
