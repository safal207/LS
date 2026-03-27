# Cooperative Meritocracy Roadmap

Date: `2026-03-27`

This roadmap defines the practical rollout plan for the cooperative meritocracy network.

It follows the current repository direction:

- `STT` hears
- `SmartEar` interprets
- `Graph memory` decides reuse
- `LLM routing / meritocracy` generates and evaluates
- future cooperative layers improve the network over time

## Current State

Already in repository:

- `InterviewUtterance` contract
- pluggable LLM backends:
  - `gonka`
  - `mimo`
  - `cloud`
  - `local`
- `MeritocracyLLMAdapter`
- Rust meritocracy skeleton
- graph memory MVP-1 building blocks:
  - `MemoryGraphStore`
  - `MemoryGraphRetriever`
  - `decide_reuse(...)`
  - `GraphMemoryRuntime`
- initial integration point in `ResonanceAgent`

## Phase 1 — Graph Memory MVP-1

Goal:

- avoid recomputing answers for repeated or near-repeated questions

Scope:

- retrieval
- `reuse / refine / full_run`
- remember successful cases

Components:

- `python/modules/graph/memory_store.py`
- `python/modules/graph/retriever.py`
- `python/modules/graph/reuse.py`
- `python/modules/graph/runtime.py`

Success criteria:

- exact match returns `reuse`
- similar match returns `refine`
- novel question returns `full_run`
- successful answers are persisted as memory cases

## Phase 2 — Trail / Pheromone Routing MVP

Goal:

- remember not only answers, but also which route produced good answers

Scope:

- route statistics
- pheromone-like reinforcement
- path selection
- route observability

New components:

- `python/modules/graph/route_stats.py`
- `python/modules/graph/path_selector.py`
- `python/modules/graph/trail_updater.py`

New concepts:

- `RouteStats`
- `PathSelectionDecision`
- `PathExecutionRecord`

Example route keys:

- `reuse`
- `refine>local`
- `full_run>local`
- `full_run>gonka`
- `full_run>local>gonka>mimo`

Success criteria:

- system stores route performance
- good routes gain weight
- poor routes decay
- selector can choose a route by prior success, not only by static config

## Phase 3 — Cooperative Roles

Goal:

- turn separate backends into coordinated contributors

Scope:

- role-based execution
- small coalition patterns
- synthesis after critique

Roles:

- `generator`
- `critic`
- `thread_guard`
- `compressor`
- `synthesizer`

Example coalition:

- `local` -> draft
- `gonka` -> critic
- `mimo` -> compressor

Success criteria:

- at least one cooperative route beats the best single backend on average
- contribution metadata is recorded

## Phase 4 — Coalition Registry

Goal:

- remember stable high-performing groupings of models

Scope:

- `CoalitionRegistry`
- trust scores
- domain/task routing by coalition strength

Example:

- technical why-questions -> `local + gonka + mimo`
- short live interview answers -> `reuse + local refine`

Success criteria:

- selector can prefer coalitions by topic and intent
- coalitions are observable and comparable

## Phase 5 — Derived Micro-Modules

Goal:

- distill repeated successful coalition behavior into cheap reusable modules

Scope:

- `DerivedModuleRegistry`
- prompt policies
- compression policies
- anti-hallucination rewrites
- domain-specific answer templates

These are not new foundation models.
They are compact reusable artifacts distilled from repeated successful cooperation.

Success criteria:

- derived modules are cheaper than parent full-run paths
- quality remains above acceptance threshold

## Phase 6 — Care Cycles

Goal:

- maintain and improve derived modules over time

Scope:

- `CareCycleRunner`
- parent coalition reviews child module outputs
- module trust increases or decreases based on quality

Success criteria:

- derived modules do not silently drift
- parent models can repair or retire weak modules

## Phase 7 — Full Cooperative Network

Goal:

- build a stable memory-aware, route-aware, cooperative network

Scope:

- memory graph
- trail graph
- coalition registry
- derived modules
- care cycles
- contribution scoring

At this stage the system no longer behaves like a flat backend router.
It behaves like a persistent cooperative network that:

- remembers prior answers
- remembers prior routes
- learns which collaborations work
- reuses work efficiently
- improves over time through structured maintenance

## Priority Order

Recommended execution order:

1. finish Graph Memory MVP-1 integration and tests
2. build Trail / Pheromone Routing MVP
3. add cooperative roles
4. add coalition registry
5. add derived micro-modules
6. add care cycles

Do not jump directly to Phase 5 or 6 before route memory is stable.

## Anti-Goals

Do not:

- move memory logic into STT
- move route logic into SmartEar
- mix provider-specific code into cooperative logic
- anthropomorphize roles directly in code
- overbuild graph databases before JSON/SQLite layers prove the need

## Related Documents

- `docs/INTERVIEW_STT_SMARTEAR_ARCHITECTURE.md`
- `docs/LLM_BACKEND_MODEL_TIERS.md`
- `docs/RUST_MERITOCRACY_CORE_PLAN.md`
- `docs/COOPERATIVE_MERITOCRACY_NETWORK.md`
