# LS Integration Roadmap

This document describes which adjacent subsystems in the repository are the best candidates for integration into `LS`, in what order, and why.

The goal is not to integrate everything at once.

The goal is to strengthen `LS` in the right sequence:

1. evaluation
2. cognition
3. portfolio control
4. federation
5. multimodal operator flow

## Integration Principles

Every integration should satisfy at least one of these outcomes:

- make decisions more measurable
- make councils more explainable
- improve human approval and operator control
- improve replay, evaluation, or governance
- improve the public research and fellowship narrative

Avoid integrations that only add conceptual complexity without improving:

- traceability
- quality
- contribution measurement
- operator usefulness
- benchmarkability

## Phase 1: Evaluation Core

### Primary integration targets

- `LiminalQA`
- `CEL`
- `CouncilContributionLedger`

### Source areas

- [docs/LIMINALQA_TEST_STRATEGY.md](LIMINALQA_TEST_STRATEGY.md)
- [docs/CI_QUALITY_GATES.md](CI_QUALITY_GATES.md)
- [python/modules/cel](../python/modules/cel)
- [python/ls/cognition](../python/ls/cognition)

### What to integrate

- connect council cycles to `LiminalQA` runs
- connect contribution, reputation, and merit updates to evaluation outcomes
- add one aggregate `council_quality_score`
- emit one combined artifact for:
  - council result
  - contribution summary
  - quality result
  - merit summary

### Why this is first

This phase gives `LS` the strongest immediate lift for:

- fellowship evidence
- operator trust
- replay and audit value
- benchmarkability

### Expected result

After this phase, `LS` can answer:

- who contributed most
- whether the cycle improved the network
- whether the output was accepted cleanly
- how that affected quality, merit, and reputation

## Phase 2: Relational Coordination

### Primary integration target

- `Relational Field Layer`

### Source areas

- [docs/architecture/RELATIONAL_FIELD_LAYER_RFC.md](architecture/RELATIONAL_FIELD_LAYER_RFC.md)
- [python/modules/field](../python/modules/field)
- [python/modules/agent](../python/modules/agent)

### What to integrate

- relation-aware routing
- trust-aware and tension-aware participant modeling
- relation-aware council scoring
- routing that accounts for:
  - trust
  - role
  - tension
  - coordination friction

### Why this is second

This phase makes the councils themselves smarter instead of only making them more measurable.

### Expected result

After this phase, `LS` can reason not only over task signals, but over:

- who is aligned
- who is conflicting
- which participants should weigh more in a given context
- which route is socially and operationally more stable

## Phase 3: Portfolio Control

### Primary integration targets

- `Market Layer`
- `AI Venture Engine`
- `Portfolio Flow Controller`

### Source areas

- [docs/AI_VENTURE_ENGINE_PFC_POSITIONING.md](AI_VENTURE_ENGINE_PFC_POSITIONING.md)
- [docs/AI_VENTURE_ENGINE_PORTFOLIO_FLOW_CONTROLLER_TZ.md](AI_VENTURE_ENGINE_PORTFOLIO_FLOW_CONTROLLER_TZ.md)
- [market_layer_mvp](../market_layer_mvp)
- [python/modules/venture](../python/modules/venture)

### What to integrate

- portfolio-aware task routing
- initiative prioritization across multiple projects
- approval + merit + contribution at portfolio level
- operator surface for:
  - bottlenecks
  - priority shifts
  - initiative health

### Why this is third

This phase upgrades `LS` from a runtime for single flows into a controller for multiple initiatives.

### Expected result

After this phase, `LS` can coordinate:

- not just one task
- but a whole stream of work, priorities, and decisions

## Phase 4: Federation

### Primary integration targets

- `Web4 mesh`
- federation protocols
- meritocracy / trust mesh

### Source areas

- [docs/WEB4_OVERVIEW.md](WEB4_OVERVIEW.md)
- [docs/WEB4_MERITOCRACY_MESH.md](WEB4_MERITOCRACY_MESH.md)
- [python/modules/web4_mesh](../python/modules/web4_mesh)
- [python/modules/protocols](../python/modules/protocols)

### What to integrate

- federated councils across LS nodes
- shared trust and merit signals
- cross-node reputation and route sharing
- basic governance-safe synchronization

### Why this is fourth

Federation matters, but it should come after the single-node evaluation and council logic are already solid.

### Expected result

After this phase, `LS` becomes:

- not only a local runtime
- but a node in a distributed coordination network

## Phase 5: Multimodal Operator Runtime

### Primary integration targets

- `SmartEar`
- `perception`
- `stt`
- screen and voice operator flow

### Source areas

- [docs/INTERVIEW_STT_SMARTEAR_ARCHITECTURE.md](INTERVIEW_STT_SMARTEAR_ARCHITECTURE.md)
- [docs/vision-v2.md](vision-v2.md)
- [python/modules/smart_ear](../python/modules/smart_ear)
- [python/modules/perception](../python/modules/perception)
- [python/modules/stt](../python/modules/stt)

### What to integrate

- multimodal context into council cycles
- operator session artifacts
- voice and screen context in approval workflows
- session-level ledger or trace outputs

### Why this is fifth

This phase makes `LS` much stronger as a live operator system, but it is less foundational than the evaluation and council layers above.

### Expected result

After this phase, `LS` can operate as:

- a coordination runtime
- an evaluation runtime
- and a multimodal operator runtime

## Recommended Order

1. `LiminalQA + CEL`
2. `Relational Field Layer`
3. `Market Layer / Portfolio Flow Controller`
4. `Web4 mesh`
5. `SmartEar / multimodal operator flow`

## Why this order is right

- first make the system measurable
- then make the councils smarter
- then make the runtime manage more than one task
- then scale it across nodes
- then deepen the interface and multimodal operator experience

## Best Near-Term Outcome

If only the first two phases are completed well, `LS` already becomes much stronger as:

- a safety and oversight artifact
- a fellowship-ready research prototype
- a real operator runtime with explainable councils

## Best Long-Term Outcome

If all five phases are completed, `LS` becomes:

- a local-first coordination runtime
- a measurable council system
- a portfolio controller
- a federated merit-aware network node
- and a multimodal operator interface
