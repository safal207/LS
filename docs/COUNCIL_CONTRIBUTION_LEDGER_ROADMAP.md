# Council Contribution Ledger Roadmap

## Purpose

This document defines the execution path for turning the existing LS coordination,
alignment, contribution, and reputation layers into one measurable council loop.

The goal is not to replace the current architecture. The goal is to connect the
existing layers so LS can answer, for each council cycle:

- who participated
- what each participant proposed
- what route or strategy was selected
- what outcome actually happened
- who contributed the most to the final win
- whether the result improved the network
- whether the answer resonated with the receiver

## Current Audit

The repository already contains most of the needed pieces.

### 1. Coordination scene state already exists

Relevant modules:

- `python/modules/agent/multi_party_alignment.py`
- `python/modules/agent/bridge_graph.py`
- `python/modules/agent/bridge_stabilization.py`
- `python/modules/agent/collective_coordination.py`
- `python/modules/agent/coordination_advisory_summary.py`

Current value:

- per-party alignment posture
- tension axes
- alignment convergence
- fragmentation and stabilization pressure
- top risk parties
- compact coordination scene summary

### 2. Strategy recommendation and feedback already exist

Relevant modules:

- `python/modules/agent/alignment_strategy_recommender.py`
- `python/modules/agent/alignment_strategy_feedback.py`
- `python/modules/agent/alignment_strategy_aggregation.py`
- `python/modules/agent/alignment_recommendation_adoption.py`
- `python/modules/agent/alignment_strategy_reputation.py`

Current value:

- recommendation generation
- recommendation adoption trace
- effective versus ineffective feedback events
- support count and effective rate
- advisory reputation overlay

### 3. Contribution and reputation already exist

Relevant modules:

- `python/modules/cel/contribution_api.py`
- `python/modules/cel/attribution_api.py`
- `python/modules/cel/reputation_engine.py`

Current value:

- contribution score
- payout split
- replayable attribution lifecycle
- per-agent reputation state

### 4. Agent cycle output already exposes most signals

Relevant module:

- `python/modules/agent/resonance_agent.py`

Current value:

- alignment report
- route metadata
- reward metadata
- cooperative metadata
- strategy recommendation bundle
- strategy feedback and calibration summaries

### 5. Strategic and product framing already exists

Relevant docs:

- `docs/positioning/coordination-advisory-one-pager.md`
- `docs/WEB4_MERITOCRACY_MESH.md`
- `docs/MERIT_LEDGER_CONSENSUS.md`

Current value:

- synergy-first architecture framing
- network benefit and merit logic
- useful contribution concept
- fairness and explainability framing

## Main Gap

The missing piece is a single cycle ledger that binds all layers together.

Today LS has:

- scene state
- recommendations
- adoption traces
- contribution scoring
- reputation scoring

But LS does not yet persist one canonical object per council cycle that answers:

- who proposed what
- what influenced the decision
- what the resulting route was
- what the real outcome was
- what the receiver did with the answer
- which participant improved the collective result the most

## Ledger Contract

The initial contract is now defined in:

- `python/ls/cognition/council_contribution_ledger.py`

Test coverage:

- `tests/test_council_contribution_ledger.py`

The contract currently includes:

- `CouncilGoal`
- `CouncilNetworkContext`
- `CouncilParticipant`
- `CouncilDecision`
- `CouncilOutcome`
- `CouncilContributionBreakdown`
- `CouncilAttribution`
- `CouncilContributionLedger`

And the builder:

- `build_council_attribution(...)`

This is the stitching contract for the next phases.

## Target State

LS should evolve into a measurable council system where:

- local and web models can participate in the same council cycle
- the final decision is traceable back to individual proposals
- contribution is measured by collective gain, not only local correctness
- receiver resonance is measured explicitly
- reputation updates are grounded in real cycle outcomes
- merit and network benefit can consume the same evidence

## Core Metrics

Each council cycle should eventually produce these metrics:

- `adoption_score`
- `outcome_lift`
- `stability_impact`
- `cost_efficiency`
- `receiver_resonance_score`
- `network_improvement`
- `path_quality`
- `council_value_score`

Derived aggregate metrics:

- local versus web contribution delta
- best contributor by cycle
- route win rate by route key
- resonance win rate by receiver type
- contribution-to-cost ratio by model
- council stability trend

## Receiver Resonance

Receiver resonance is required for the full objective.

It should measure whether the result was not only logically acceptable, but
also received in a way that reduced friction and improved alignment.

Initial MVP signals:

- operator intervention required or not
- operator feedback score
- downstream model acceptance or rejection
- revision count after first answer
- softening detected
- adoption coverage

## Execution Phases

### Phase 1. Ledger Foundation

Objective:

- keep the ledger contract stable and tested

Actions:

- keep `council_contribution_ledger.py` as the canonical cycle schema
- export it from `python/ls/cognition/__init__.py`
- keep dedicated schema tests passing

Done when:

- schema is importable
- schema tests pass
- no runtime wiring yet required

### Phase 2. Council Cycle Ingestion

Objective:

- produce one ledger per real council cycle

Actions:

- identify the orchestration point that has access to:
  - recommendations
  - route decision
  - outcome
  - feedback summaries
- build `CouncilParticipant` objects from council/model participants
- derive `CouncilDecision` from selected route and adopted proposals
- derive `CouncilOutcome` from real cycle outcome fields
- emit one JSON artifact per cycle

Expected artifact:

- `artifacts/council-ledger/<cycle_id>.json`

Current status:

- MVP implemented through `ResonanceAgent._build_output(...)`
- one council ledger artifact is now emitted per completed cycle when the
  council ledger contract is available
- output now exposes:
  - `council_contribution_ledger`
  - `council_contribution_ledger_artifact`

### Phase 3. Receiver Resonance Layer

Objective:

- add receiver acceptance and resonance as first-class outcome signals

Actions:

- define `receiver_type`
- define `receiver_resonance_score`
- define `receiver_acceptance_label`
- wire in operator and downstream-model feedback

Expected result:

- cycle outcome reflects both correctness and resonance

Current status:

- MVP implemented in council outcome fields:
  - `receiver_type`
  - `receiver_resonance_score`
  - `receiver_acceptance_label`
- current `ResonanceAgent` wiring derives resonance from live cycle signals:
  - softening score
  - goal alignment
  - cooperative participation
  - intervention requirement

### Phase 4. Reputation and Contribution Sync

Objective:

- update contribution and reputation from real council cycles

Actions:

- map ledger contribution scores into CEL contribution APIs
- update reputation from:
  - quality
  - contribution
  - resonance
- preserve replayability for audit

Expected result:

- reputation becomes cycle-grounded rather than event-fragmented

### Phase 5. Merit and Network Benefit Sync

Objective:

- connect council quality to Web4 merit logic

Actions:

- map contribution and network improvement into merit signals
- connect cycle-level improvement to `NetworkEffectBonus` style logic
- compare selfish versus synergy-positive paths

Expected result:

- the network rewards useful collective contribution, not only isolated output

### Phase 6. Dashboard and Analysis

Objective:

- make council performance inspectable by humans

Actions:

- add council analytics summary output
- expose trend reports:
  - best contributor
  - local versus web lift
  - route quality
  - receiver resonance
  - council stability

Expected views:

- CLI summary
- JSON artifacts
- optional local dashboard panel

## Development Order

The implementation order for this roadmap is:

1. land the ledger contract and roadmap
2. wire ledger generation into one real orchestration path
3. add receiver resonance fields
4. sync ledger to CEL contribution and reputation
5. expose trend reporting
6. connect to merit and network-level reward logic

## Git Sync Rule

Every phase should end with:

- passing tests for the touched surface
- one focused commit
- push to `origin/main`
- roadmap update with current status

This roadmap is the source of truth for the next integration steps.
