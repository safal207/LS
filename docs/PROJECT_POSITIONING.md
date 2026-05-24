# LS Project Positioning

## One-line Positioning

**LS is a cooperative precision layer for AI co-work.**

It does not try to make models magically smarter. It makes repeated cooperation
between humans, models, agents, and tools more precise by checking continuity,
evidence, consent, routes, and contributions before outputs become actions or
memory.

## Core Thesis

```text
model intelligence stays external
network precision compounds inside LS
```

Every useful AI work session should be able to leave a trace:

```text
task
-> route
-> evidence
-> contribution
-> decision
-> reusable artifact
```

The next similar task should start from a better known route, not from zero.

## Product Atom

The smallest durable product artifact is now a **Cognitive Trail Run**.

```text
Cognitive Trail Run = one recorded measurable cooperation route
```

A trail run records:

- what task was attempted;
- which roles and actors participated;
- what evidence was produced;
- which role or actor contributed value;
- what result was achieved;
- whether the route should be repeated.

This keeps the claim narrow and measurable:

```text
LS does not make a model smarter.
LS measures which cooperative route made a concrete task more precise.
```

See:

- `docs/COGNITIVE_TRAIL_RUN_CONTRACT.md`
- `docs/COOPERATIVE_PRECISION_METRICS.md`
- `schemas/cognitive_trail_run.schema.json`
- `examples/trails/pr_review_small_run.json`
- `examples/trails/pr_review_cooperative_result.json`

## The Problem

Modern AI work is becoming multi-agent and multi-model, but most systems still
treat each answer as an isolated event.

That creates five failure modes:

- context breaks and agents continue anyway;
- outputs become action without enough evidence;
- useful sessions disappear into chat history;
- teams cannot tell which route produced value;
- model reputation is confused with verified contribution.

## What LS Adds

LS adds a local-first layer around agent work:

```text
continuity before continuation
evidence before action
consent before memory
contribution before reputation
precision before scale
```

In practice, LS can:

- route raw agent output through governance before it reaches the user;
- detect broken session continuity;
- hold risky actions until evidence is present;
- turn useful sessions into human-reviewed growth proposals;
- remember which cooperative routes worked;
- produce artifacts that can be replayed, audited, and improved.

## First Product Wedge

The first narrow use case is:

```text
AI Code Review / PR Review Trail Network
```

Why this wedge works:

- git diffs are concrete evidence;
- tests and CI provide external signals;
- review comments can validate or reject findings;
- routes are easy to compare;
- contributors understand the workflow.

Current proof commands:

```bash
python scripts/run_pr_review_trail_demo.py
python scripts/run_pr_review_trail_artifact.py
```

This demonstrates the core loop:

```text
real diff
-> draft reviewer / risk critic / evidence verifier / final reviewer
-> signals
-> route reward
-> reusable review artifact
```

## Strategic Layers

### 1. Agent Gateway

Agents can propose answers, memory writes, or actions. LS checks whether the
proposal has enough continuity, authority, and evidence to continue.

### 2. Cognitive Trail Network

Cooperative routes leave route artifacts. Strong routes gain weight. Weak routes
decay. The network becomes more precise at repeated work.

A Cognitive Trail Run is the concrete route artifact that makes this layer
measurable.

### 3. Contribution Ledger

LS should measure who contributed verified value inside a route:

- who found a real risk;
- who provided evidence;
- who reduced hallucination risk;
- who produced unsupported claims;
- whose contribution helped the final decision.

### 4. Cooperative Role Market

Repeated work is not only a model-selection problem. It is a role-matching
problem:

```text
customer -> consumer -> designer -> executor -> verifier -> operator
```

LS should learn which role arrangement produces verified value, not only which
single model answered best.

See:

- `docs/COOPERATIVE_ROLE_MARKET.md`

### 5. Depth Economy / Meta-Interaction

Not every task should run at the same depth. LS should decide whether the task
is a simple execution problem, a design-synergy problem, or a deeper
customer-consumer problem:

```text
executor:            1 + 1 = 2
designer:            1 + 1 = 3
customer / consumer: 1 + 1 = n
```

The Amygdala layer can regulate when to execute directly, design for synergy,
deepen the customer-consumer pair, expand the stakeholder radius, or hold for
human review.

See:

- `docs/DEPTH_ECONOMY_LAYER.md`
- `docs/AMYGDALA_LAYER_MAP.md`

### 6. Personal Cognitive Garden

Useful AI sessions can become human-owned development memory: goals, skills,
decisions, constraints, evidence, reflections, and growth paths. This must stay
private by default and require human review.

## Category

LS sits between several known categories:

```text
multi-agent orchestration
+ AI safety / oversight
+ agent gateway
+ route memory
+ contribution ledger
+ cooperative role market
+ local-first personal AI layer
```

The clean external category is:

```text
cooperative precision infrastructure for AI co-work
```

## What LS Is Not

LS is not:

- another chatbot;
- a claim that models become generally smarter;
- a general model benchmark;
- a surveillance dashboard;
- an autonomous action system without human authority;
- a claim that AI safety is solved.

LS is one auditable primitive:

```text
verified cooperative route memory before continuation, action, memory, or reputation
```

## Audience-Specific Framing

| Audience | Lead with | Avoid leading with |
|---|---|---|
| Contributors | Cooperative Precision Network and PR-review trails | Abstract cognition language |
| Maintainers | Review artifacts, route memory, contribution scoring | Generic agent automation |
| Grant reviewers | Local-first evidence, consent, anti-surveillance, auditability | Hype about smarter AI |
| Safety researchers | Continuity, evidence gates, replayable route artifacts | Claims of solved alignment |
| Operators | Agents pass through your rules before output becomes action | More dashboards |

## Short Lines

> LS does not make models smarter. LS makes their cooperation more precise.

> LS remembers not only answers, but the routes that produced verified value.

> Every verified session reduces uncertainty for the next one.

> Agents propose. LS checks whether the route, evidence, and consent are strong
> enough to continue.

## Русская Короткая Версия

**LS — это слой точности кооперации для работы человека и ИИ.**

LS не делает модели “умнее” магически. Он делает их совместную работу точнее:
проверяет контекст, доказательства, согласие, маршрут работы и вклад участников
до того, как ответ станет действием, памятью или репутацией.

Короткая формула:

```text
интеллект остается в моделях
точность накапливается в сети LS
```

Первый прикладной вход — PR-review: реальный git diff превращается в проверяемый
артефакт с маршрутом, сигналами риска, вкладом и route reward.
