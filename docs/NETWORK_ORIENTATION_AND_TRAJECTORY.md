# Network Orientation And Trajectory

Date: `2026-03-27`

This document defines the next control layer above graph memory, trail routing, coalitions, and derived modules.

Vocabulary companion:

- `docs/NETWORK_VOCABULARY.md`
- `docs/NETWORK_OPERATIONS.md`

The goal is to give the network:

- a single orientation center for choosing routes, coalitions, and derived modules
- a retrospective council for structured review of past behavior
- a temporal trajectory layer for seeing the network in past, present, and future
- a cognitive adequacy core that prevents drift, incoherence, and unsafe reinforcement

## Core Principle

This layer does not replace:

- `STT`
- `SmartEar`
- backend adapters
- `ResonanceAgent`

It coordinates them.

The purpose is not to move generation logic upward.
The purpose is to make the whole network self-orienting, self-reviewing, and temporally aware.

## High-Level Flow

```text
Question
-> SmartEar
-> OrientationCenter
-> ExecutionPlan
-> GraphMemory / Route / Coalition / DerivedModule path
-> FinalAnswer
-> RetrospectiveCouncil
-> TemporalTrajectoryLayer
-> CognitiveAdequacyCore
-> network updates
```

## Main Layers

### Orientation Center

The Orientation Center is the single entry point for network-level decision making.

It knows:

- which memory cases are relevant
- which routes are strong
- which coalitions are trusted
- which derived modules are cheap and safe
- when to prefer `reuse`, `refine`, `full_run`, cooperative execution, or derived-module execution

Responsibilities:

- unify question/answer memory, route memory, coalition memory, and derived-module memory
- choose the execution mode for the current question
- produce a structured execution plan
- provide a stable control surface for the rest of the network

Suggested file:

- `python/modules/network/orientation_center.py`

### Retrospective Council

The Retrospective Council is the analysis layer that looks backward.

It does not answer the user directly.
It reviews the network's past runs.

Responsibilities:

- analyze recent executions
- compare route performance over time
- compare coalition performance over time
- detect weak or stale derived modules
- produce explicit recommendations

Suggested files:

- `python/modules/network/retrospective_council.py`
- `python/modules/network/reports.py`

Example output:

```json
{
  "weak_routes": ["full_run>cloud"],
  "strong_coalitions": ["full_run>local>gonka>mimo"],
  "stale_modules": ["derived-generic-generic-local"],
  "recommendations": [
    "reduce trust for cloud-only route",
    "promote local-gonka-mimo coalition for technical_reasoning"
  ]
}
```

### Temporal Trajectory Layer

The Temporal Trajectory Layer gives the network time awareness.

It lets the network see:

- what it was
- what it is
- what it is becoming

It is not mystical forecasting.
It is structured temporal analysis of network behavior.

Responsibilities:

- store periodic snapshots of route, coalition, derived-module, and adequacy state
- compare current state to prior states
- detect improvement, decay, over-concentration, and drift
- build future scenarios based on current trends

Suggested files:

- `python/modules/network/trajectory_store.py`
- `python/modules/network/trajectory_analyzer.py`
- `python/modules/network/future_planner.py`

### Cognitive Adequacy Core

The Cognitive Adequacy Core is the sanity layer.

Its job is to keep the network coherent and safe.

Responsibilities:

- detect drift in derived modules
- detect route dominance without adequacy
- detect coalition trust inflation
- prevent reinforcement of noisy, off-thread, or hallucination-prone behavior
- maintain consistency of style, grounding, and thread alignment

Suggested file:

- `python/modules/network/cognitive_adequacy.py`

Current MVP behavior:

- produces `stable / watch / intervene`
- tightens `derived module` admission thresholds when the network is in `watch`
- blocks easy promotion paths and forces more exploration when the network is in `intervene`
- feeds adequacy metadata back into `OrientationCenter`

### Observer Report

The current control layer now also supports a unified observer view:

- `RetrospectiveCouncil`
- `TemporalTrajectoryLayer`
- `CognitiveAdequacyCore`

These are aggregated into one `ObserverReport`, so routing code does not need
to manually reconcile three different reports.

## New Data Objects

### NetworkExecutionPlan

```python
@dataclass
class NetworkExecutionPlan:
    mode: str
    route_key: str | None
    coalition_id: str | None
    derived_module_id: str | None
    memory_case_id: str | None
    reason: str
    confidence: float
```

### NetworkSnapshot

```python
@dataclass
class NetworkSnapshot:
    snapshot_id: str
    timestamp: str
    route_health: dict
    coalition_health: dict
    derived_module_health: dict
    adequacy_score: float
    latency_score: float
    drift_score: float
```

### TrajectoryRecord

```python
@dataclass
class TrajectoryRecord:
    period: str
    previous_snapshot_id: str
    current_snapshot_id: str
    deltas: dict
    trend: str
    risks: list[str]
    opportunities: list[str]
```

### FutureScenario

```python
@dataclass
class FutureScenario:
    scenario_id: str
    title: str
    assumptions: list[str]
    expected_benefits: list[str]
    expected_risks: list[str]
    projected_adequacy: float
    projected_cost: float
```

## Time Windows

### Past View

The network should be able to answer:

- which routes were strong last week
- which coalitions improved
- which derived modules regressed
- where hallucination risk increased
- where the network wasted cost

### Present View

The network should be able to answer:

- what the dominant route is now
- which coalition is currently strongest
- which derived modules are trusted now
- whether drift is currently low or high
- whether the current network state is coherent

### Future View

The network should be able to simulate:

- what happens if derived modules are promoted aggressively
- what happens if exploration is reduced too much
- what happens if one coalition becomes over-dominant
- what happens if care cycles are skipped

This is scenario planning, not prophecy.

## Orientation Center Responsibilities In Detail

The Orientation Center should unify these stores:

- `MemoryGraphStore`
- `RouteStatsStore`
- `CoalitionRegistry`
- `DerivedModuleRegistry`

And expose one method:

```python
decide(item) -> NetworkExecutionPlan
```

The rest of the network should not need to manually inspect 4 different registries.

With the adequacy core connected, `OrientationCenter` also becomes the place where:

- `derived modules` can be held back when drift is rising
- route exploration can be increased when one path dominates without enough adequacy
- network-level safety signals affect execution before response generation

## Retrospective Council Responsibilities In Detail

The Retrospective Council should answer questions like:

- which routes are improving over time
- which coalitions are decaying
- which derived modules are cheap but unsafe
- where network adequacy is dropping
- where cost is growing faster than quality

This layer should be report-oriented first.
Do not start by making it autonomous.

## Temporal Trajectory Metrics

Suggested tracked metrics:

- route concentration
- route adequacy
- coalition stability
- derived-module trust trend
- derived-module drift score
- average thread relevance
- average hallucination risk
- reuse efficiency
- cost per accepted answer
- latency per accepted answer

## Cognitive Adequacy Guardrails

Examples:

- do not promote a derived module if hallucination risk is high
- do not let one route dominate only because it is cheap
- do not keep a coalition highly trusted if thread relevance falls
- do not allow silent drift in derived-module policy text

The core should prefer:

- stable adequacy over superficial speed
- coherent network identity over opportunistic shortcuts

## Rollout Order

Recommended order:

1. `Phase 6` — `CareCycleRunner`
2. `Phase 7` — `OrientationCenter`
3. `Phase 8` — `TemporalTrajectoryLayer`
4. `Phase 9` — `CognitiveAdequacyCore`

Reason:

- care cycles stabilize derived modules
- orientation center unifies control
- temporal layer adds self-history
- adequacy core becomes meaningful only once the network has enough structure to evaluate

## Anti-Goals

Do not:

- push this logic into `SmartEar`
- push this logic into backend adapters
- make future planning opaque or mystical
- let the adequacy core silently override everything without observability
- collapse orientation, retrospection, trajectory, and adequacy into one giant class

## Relationship To Existing Phases

- `Phase 1` gave the network case memory
- `Phase 2` gave the network route memory
- `Phase 3` gave the network cooperative role execution
- `Phase 4` gave the network coalition memory
- `Phase 5` gave the network derived micro-modules
- this document defines the control layer above those pieces

## Practical MVP Recommendation

Do not build all four layers at once.

Start with:

1. `OrientationCenter`
2. lightweight retrospective report

Then add:

3. snapshot storage
4. trajectory comparison

Only after that add:

5. adequacy core promotion / demotion rules
