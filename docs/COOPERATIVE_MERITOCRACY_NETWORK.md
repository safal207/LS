# Cooperative Meritocracy Network

This document defines a practical design for a cooperative multi-model network on top of the existing interview pipeline.

Related control-layer design:

- `docs/NETWORK_ORIENTATION_AND_TRAJECTORY.md`

The goal is not only to rank backend answers, but to let the network:

- reuse prior solutions instead of regenerating everything
- coordinate multiple models through complementary roles
- synthesize a stronger final answer from multiple candidates
- assign contribution credit fairly
- grow small derived modules from stable model coalitions

## Core Principle

This layer sits above `SmartEar` and above raw backend routing.

- `STT` still only hears
- `SmartEar` still only interprets
- `LLM backends` still only generate
- the new layer coordinates reuse, cooperation, synthesis, and memory

Do not move this logic into STT or backend adapters.

## High-Level Flow

```text
Question
-> SmartEar
-> MemoryGraphRetriever
-> ReuseDecision
-> CooperativeGraphEngine
-> MeritocracySelector
-> SynthesisAgent
-> FinalAnswer
-> MemoryGraphUpdater
-> ContributionScorer
```

## System Goals

1. Reuse prior answers when the same or a very similar question appears again.
2. Reduce unnecessary token and latency cost.
3. Let multiple backends contribute through complementary roles.
4. Select the strongest answer without losing useful fragments from weaker candidates.
5. Track who improved the final answer and by how much.
6. Distill frequent successful collaborations into cheaper specialized micro-modules.

## New Concepts

### Coalition

A coalition is a stable group of backends that work well together for a certain task.

Example:

- `gonka` as strategist
- `mimo` as simplifier
- `local` as fast drafter

### Derived Micro-Module

A derived micro-module is a compact reusable artifact that comes out of repeated successful coalition behavior.

Examples:

- compact prompt policy
- anti-hallucination rewriter
- short interview answer compressor
- domain-specific explanation template
- lightweight classifier for reuse decisions

These are not new foundation models. They are cheap, task-specific modules distilled from successful coalition behavior.

### Care Cycle

A care cycle is a scheduled or triggered maintenance pass where larger parent backends evaluate and improve a derived micro-module.

Examples:

- review recent module outputs
- generate corrections
- increase or decrease trust
- replace the module if quality regresses

## Main Components

### MemoryGraphStore

Persistent storage for reusable network knowledge.

Responsibilities:

- store normalized questions
- store past answers and quality
- store embeddings or similarity keys
- store contribution records
- store coalition performance
- store derived micro-module metadata

Suggested first implementation:

- SQLite or JSONL

Do not start with a graph database unless there is a real scaling need.

### MemoryGraphRetriever

Finds similar prior cases for a new question.

Responsibilities:

- semantic similarity lookup
- retrieve best prior cases
- retrieve prior winning coalitions
- return best prior answer and confidence

### ReuseDecision

Determines whether the system should:

- `reuse`
- `refine`
- `full_run`

Suggested thresholds:

- similarity `>= 0.92` -> `reuse`
- similarity `>= 0.78 and < 0.92` -> `refine`
- similarity `< 0.78` -> `full_run`

### CooperativeGraphEngine

Runs the active coalition for the current question.

Responsibilities:

- assign roles to models
- pass prior memory when relevant
- generate candidate answers
- generate critiques
- generate thread-alignment checks
- produce synthesis inputs

### MeritocracySelector

Ranks candidates and synthesis outputs.

Responsibilities:

- compute answer quality scores
- apply acceptance thresholds
- choose winner or escalate to synthesis

### SynthesisAgent

Builds the final answer from top candidates when collaboration is better than a single winner.

Responsibilities:

- merge best fragments
- remove contradictions
- preserve thread alignment
- preserve factual caution

### ContributionScorer

Assigns fair credit to contributors.

Responsibilities:

- score delta in answer quality after each contribution
- reward useful critique and useful synthesis
- track long-term coalition strength

### CoalitionRegistry

Tracks stable partnerships and groupings.

Responsibilities:

- remember which coalitions work well
- track domains and task types
- store trust scores
- support adaptive routing

### DerivedModuleRegistry

Stores distilled micro-modules that can answer or refine cheaply.

Responsibilities:

- store module metadata
- track trust and usage
- define parent coalition
- allow quick reuse before expensive backend calls

### CareCycleRunner

Runs maintenance over derived micro-modules.

Responsibilities:

- validate module quality
- request parent correction passes
- promote or demote modules
- mark modules stale or unsafe

## Core Data Objects

### NetworkQuestion

```python
@dataclass
class NetworkQuestion:
    text: str
    clean_text: str
    intent: str | None
    why: str | None
    strategy: dict | None
    thread_context: str | None
    embedding: list[float] | None = None
```

### MemoryCase

```python
@dataclass
class MemoryCase:
    case_id: str
    question_text: str
    clean_text: str
    intent: str | None
    why: str | None
    answer_text: str
    answer_quality: dict
    contributors: list[dict]
    embedding: list[float] | None = None
    reuse_count: int = 0
```

### ReuseDecision

```python
@dataclass
class ReuseDecision:
    mode: str  # reuse / refine / full_run
    matched_case_id: str | None
    similarity: float
    reason: str
```

### GraphCandidate

```python
@dataclass
class GraphCandidate:
    backend: str
    model: str
    role: str
    answer: str
    quality: dict
    source_case_id: str | None = None
    used_prior_memory: bool = False
```

### GraphEdge

```python
@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str  # critique / support / refine / synthesize
    payload: dict
```

### Coalition

```python
@dataclass
class Coalition:
    coalition_id: str
    members: list[str]
    roles: dict[str, str]
    trust_score: float
    topic_domains: list[str]
```

### DerivedModule

```python
@dataclass
class DerivedModule:
    module_id: str
    parent_coalition_id: str
    domain: str
    task_type: str
    policy_type: str  # prompt / heuristic / classifier / adapter
    quality_score: float
    usage_count: int
```

### ContributionRecord

```python
@dataclass
class ContributionRecord:
    backend: str
    model: str
    role: str
    delta_score: float
    accepted_fragments: int
    rejected_fragments: int
    helped_final_answer: bool
```

## Role Model

Backends should be assigned complementary roles, not treated as identical generators.

Possible roles:

- `generator`
- `critic`
- `thread_guard`
- `synthesizer`
- `compressor`
- `fact_guard`
- `style_guard`

Example coalition:

- `local` -> `generator`
- `gonka` -> `critic`
- `mimo` -> `compressor`
- `cloud` -> `thread_guard`

## Reuse Strategy

### Reuse

Use the prior answer directly if similarity is very high and prior quality is trusted.

### Refine

Use the prior answer as the base draft and ask one or two coalition members to:

- verify it
- adapt it to current thread context
- compress it

### Full Run

Do a fresh cooperative generation when the question is sufficiently new.

## Meritocracy Score

Suggested score:

```text
score =
  0.30 * adequacy
+ 0.25 * relevance
+ 0.20 * thread_relevance
+ 0.15 * coherence
+ 0.10 * reuse_bonus
- 0.25 * hallucination_risk
- 0.10 * latency_penalty
```

Additional fields to support:

- `reuse_bonus`
- `memory_alignment`
- `delta_from_prior`

## Contribution Scoring

Suggested contribution credit:

```text
agent_credit =
  0.50 * delta_overall
+ 0.20 * delta_relevance
+ 0.20 * delta_thread_relevance
+ 0.10 * hallucination_reduction
```

This rewards:

- useful generation
- useful critique
- useful synthesis
- safety improvements

It does not reward only the final winner.

## Lifecycle of a Derived Micro-Module

1. Coalition repeatedly performs well on the same task pattern.
2. System distills a small reusable module from this behavior.
3. Module is registered with initial trust.
4. Module is used for similar questions when cheap reuse is preferred.
5. CareCycleRunner checks whether the module still performs well.
6. Parent coalition improves, demotes, or replaces the module.

## Integration With Current Repository

Keep existing layers intact.

Current core:

```text
STT -> SmartEar -> LLM routing / Meritocracy -> ResonanceAgent
```

Expanded target:

```text
STT
-> SmartEar
-> MemoryGraphRetriever
-> CooperativeGraphEngine
-> MeritocracySelector
-> SynthesisAgent
-> ResonanceAgent final polish
-> FinalAnswer
-> MemoryGraphUpdater
```

## Suggested File Layout

```text
python/modules/graph/memory_store.py
python/modules/graph/retriever.py
python/modules/graph/reuse.py
python/modules/graph/coalitions.py
python/modules/graph/derived_modules.py
python/modules/graph/cooperative_engine.py
python/modules/graph/synthesis.py
python/modules/graph/contribution.py
python/modules/graph/care_cycle.py
```

## MVP Rollout

### Phase 1

- `MemoryGraphStore`
- `MemoryGraphRetriever`
- `ReuseDecision`
- reuse/refine/full-run policy

This gives immediate resource savings.

### Phase 2

- `CooperativeGraphEngine`
- `critic`
- `synthesizer`
- `ContributionScorer`

This gives better answer quality and fairer credit assignment.

### Phase 3

- `CoalitionRegistry`
- `DerivedModuleRegistry`
- `CareCycleRunner`

This gives long-term adaptive improvement of the network.

## Constraints

- Do not put coalition logic in STT.
- Do not put memory-graph logic in backend adapters.
- Do not anthropomorphize role design in code.
- Do not create heavy online learning loops before retrieval and reuse are stable.
- Do not start with a large graph database.

## Recommended First MVP

Build these first:

1. `MemoryGraphStore`
2. `MemoryGraphRetriever`
3. `ReuseDecision`
4. one cooperative path:
   - `local` as draft generator
   - `gonka` as critic
   - `mimo` as compressor
5. `ContributionScorer`

This is the smallest version that turns simple routing into a cooperative, memory-aware network.

## Related Documents

- `docs/INTERVIEW_STT_SMARTEAR_ARCHITECTURE.md`
- `docs/LLM_BACKEND_MODEL_TIERS.md`
- `docs/RUST_MERITOCRACY_CORE_PLAN.md`
- `docs/COOPERATIVE_MERITOCRACY_ROADMAP.md`
