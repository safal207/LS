# Network Vocabulary

Date: `2026-03-27`

This document defines the high-level vocabulary for the cooperative network.

It is not a replacement for implementation docs.
It is the shared conceptual layer above:

- graph memory
- route memory
- coalition memory
- derived micro-modules
- care cycles
- orientation and trajectory logic

## Core Mapping

- **Need** -> why the network should move at all
- **Energy** -> how much compute, urgency, and attention the network can spend
- **Goal** -> what kind of answer the network is trying to produce
- **Vector** -> the direction of the decision
- **Trajectory** -> the route the network actually takes
- **Phases** -> the rhythm and order of the route
- **Orientation Center** -> the axis of stability
- **Tuning Fork** -> the reference for coherence and adequacy
- **Observer** -> the condition of self-correction

## Need

Need is the reason the network activates.

Examples:

- a user asked a new question
- memory did not provide a sufficient answer
- a prior route looks weak for this task
- the question is urgent and requires a quick decision

Engineering translation:

- `NeedProfile`
- `need_score`
- `priority`
- `compute_budget`

Current MVP:

- `NeedProfiler` derives a lightweight `NeedProfile` from:
  - question wording
  - graph similarity / memory gap
  - observer status
- `NetworkControlCenter` attaches this profile to the execution plan

## Energy

Energy is the usable resource available to satisfy the need.

Examples:

- latency budget
- token budget
- whether reuse is available
- whether only cheap local execution is acceptable

Engineering translation:

- `compute_budget`
- `latency_budget_ms`
- `cost_budget`
- `fallback_budget`

## Goal

Goal is the answer profile the network wants to reach.

Examples:

- concise answer
- high thread relevance
- low hallucination risk
- strong coherence
- acceptable latency

Engineering translation:

- `GoalVector`
- `target_quality_profile`

## Vector

Vector is the direction of the solution.

Examples:

- prefer factual caution over fluency
- prefer speed over deep synthesis
- prefer reuse over full regeneration
- prefer coalition path over single backend

Engineering translation:

- `decision_direction`
- `quality_priority`
- `route_preference`

## Trajectory

Trajectory is the concrete route through the network.

Examples:

- `reuse`
- `refine>local`
- `full_run>local>gonka>mimo`
- `derived>local`

Engineering translation:

- `ExecutionTrajectory`
- `route_key`
- `execution_plan`

## Phases

Phases are the ordered steps inside the trajectory.

Examples:

- draft
- critique
- compress
- review
- care cycle

Engineering translation:

- `phase_state`
- `phase_schedule`
- `pipeline_stage`

## Orientation Center

The Orientation Center is the stable control point of the network.

It decides:

- whether to reuse, refine, or run fully
- whether to use a coalition
- whether to use a derived module
- which route is most adequate now

Engineering translation:

- `OrientationCenter`

## Tuning Fork

The Tuning Fork is the reference profile for a coherent answer.

It defines what “good alignment” means for the network.

Examples:

- high relevance
- high thread alignment
- low hallucination risk
- acceptable latency
- stable style

Engineering translation:

- `TuningFork`
- `AdequacyProfile`
- `ReferenceQualityProfile`

## Observer

The Observer is the self-correction condition of the network.

It does not generate the answer directly.
It notices deviation and triggers correction.

Examples:

- derived module drift
- route over-dominance
- coalition trust inflation
- loss of thread relevance
- rising hallucination risk

Engineering translation:

- `RetrospectiveCouncil`
- `TemporalTrajectoryLayer`
- `CognitiveAdequacyCore`

## Suggested Core Objects

### NeedProfile

```python
@dataclass
class NeedProfile:
    urgency: float
    novelty: float
    uncertainty: float
    memory_gap: float
    compute_budget: float
```

### GoalVector

```python
@dataclass
class GoalVector:
    target_relevance: float
    target_thread_alignment: float
    target_hallucination_max: float
    target_latency_ms: float
    style: str
```

### ExecutionTrajectory

```python
@dataclass
class ExecutionTrajectory:
    route_key: str
    phases: list[str]
    expected_cost: float
    expected_quality: float
```

### TuningFork

```python
@dataclass
class TuningFork:
    adequacy_target: float
    coherence_target: float
    thread_target: float
    hallucination_ceiling: float
```

### ObserverReport

```python
@dataclass
class ObserverReport:
    drift_detected: bool
    route_instability: bool
    coalition_instability: bool
    module_decay: bool
    recommendation: str
```

## Practical Use

This vocabulary is useful when designing:

- `OrientationCenter`
- `RetrospectiveCouncil`
- `TemporalTrajectoryLayer`
- `CognitiveAdequacyCore`

It also gives the project one stable language for discussing:

- why the network moved
- where it moved
- how it moved
- whether it stayed coherent
- whether it corrected itself

## One-Line Summary

```text
Need launches the network.
Goal directs the network.
Trajectory carries the network.
Phases organize the network.
Orientation Center stabilizes the network.
Tuning Fork tunes the network.
Observer corrects the network.
```
