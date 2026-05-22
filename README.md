# LS — Cooperative Precision Layer for AI Co-work

[English](#english) | [Русский](#russian)

---

<a name="english"></a>

# LS — Cooperative Precision Layer for AI Co-work

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
Cooperative precision: [Reviewer Quickstart](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md) · [Roadmap](docs/COOPERATIVE_PRECISION_ROADMAP.md) · [Cognitive Trail Network](docs/COGNITIVE_TRAIL_NETWORK.md) · [PR Role Market Benchmark](docs/PR_ROLE_MARKET_BENCHMARK.md)
Positioning: [Project Positioning](docs/PROJECT_POSITIONING.md)

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

Reviewer quickstart for Cognitive Trail validation:

```bash
python3 scripts/validate_cognitive_trail_runs.py
python3 scripts/generate_pr_review_trail_run.py --last 10 --validate
```

See: [`docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md`](docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md)

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