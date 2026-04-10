# Validation & Governance System

Three cooperating layers that turn candidate answers into an auditable,
tamper-resistant consensus decision.

```
CandidateAnswer × N
       │
       ▼
┌──────────────────────────┐
│  CollectiveAnswerValidator│  ← decides the winner
└──────────────┬───────────┘
               │ ValidationResult
               ▼
┌──────────────────────────┐
│  LifetraValidationAdapter │  ← records the decision as a trace artifact
└──────────────┬───────────┘
               │ ValidationTraceArtifact
               ▼
┌──────────────────────────┐
│  ValidationGovernanceEngine│ ← inspects history, reputation, coalitions
└──────────────┬───────────┘
               │ ValidationGovernanceReport
               ▼
          ValidationResult
     (with trace + governance attached)
```

---

## Quick start

```python
from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
)
from ls.cognition.lifetra_validation_adapter import LifetraValidationAdapter
from ls.cognition.validation_governance import (
    InMemoryValidationHistoryStore,
    ValidationGovernanceEngine,
)

store  = InMemoryValidationHistoryStore()
engine = ValidationGovernanceEngine(history_store=store)
adapter = LifetraValidationAdapter()          # uses lifetra_py if available

validator = CollectiveAnswerValidator(
    trace_backend=adapter,
    governance_engine=engine,
)

payload = ValidationInput(
    task_prompt="Which caching strategy should we use?",
    candidates=[
        CandidateAnswer(
            agent_id="agent-a",
            answer_text="LRU with a 300-second TTL.",
            relevance=0.88,
            thread_relevance=0.82,
            hallucination_risk=0.07,
            supports=["agent-b"],
        ),
        CandidateAnswer(
            agent_id="agent-b",
            answer_text="TTL-based LRU cache, evict stale entries after 5 minutes.",
            relevance=0.81,
            thread_relevance=0.79,
            hallucination_risk=0.09,
        ),
        CandidateAnswer(
            agent_id="agent-c",
            answer_text="Cache everything forever, never evict.",
            relevance=0.22,
            thread_relevance=0.20,
            hallucination_risk=0.74,
        ),
    ],
)

result = validator.validate(payload)

print(result.winner_agent_id)           # "agent-a"
print(result.consensus_status)          # "convergent"
print(result.trace_artifact.trace_id)   # "lifetra:a3f9…"
print(result.governance_report.review_required)  # False
```

---

## Layer 1 — CollectiveAnswerValidator

The only component that decides which answer wins.
Its output is a `ValidationResult` with a stable, deterministic contract.

### Input

| Field | Type | Description |
|---|---|---|
| `task_prompt` | `str` | The question or task posed to all agents |
| `candidates` | `Sequence[CandidateAnswer]` | One entry per agent |

Each `CandidateAnswer`:

| Field | Type | Notes |
|---|---|---|
| `agent_id` | `str` | Unique identifier for the agent |
| `answer_text` | `str` | The raw answer |
| `relevance` | `float` [0–1] | How relevant the answer is to the task |
| `thread_relevance` | `float` [0–1] | How relevant to the ongoing conversation thread |
| `hallucination_risk` | `float` [0–1] | Estimated probability of confabulation |
| `supports` | `Sequence[str]` | agent_ids this answer supports |
| `contradicts` | `Sequence[str]` | agent_ids this answer contradicts |

### Scoring formula

```
score = 0.4 × relevance
      + 0.3 × thread_relevance
      + 0.1 × min(support_count, 3) / 3
      − 0.2 × hallucination_risk
      − 0.1 × min(contradiction_count, 3) / 3
```

Clamped to `[0.0, 1.0]`.

### Acceptance thresholds

A candidate is accepted only when **all** of the following hold:

- `score ≥ 0.45`
- `relevance ≥ 0.30`
- `thread_relevance ≥ 0.30`
- `hallucination_risk ≤ 0.65`
- `answer_text` is not blank

### Consensus statuses

| Status | Meaning |
|---|---|
| `convergent` | ≥ 2 accepted, top two within 0.15 score difference |
| `weak` | Only 1 accepted, or winner is far ahead of runner-up |
| `conflicted` | ≥ 2 accepted, but cross-contradictions exist between them |
| `rejected` | No candidate met acceptance criteria |

### Global risk flags

| Flag | Raised when |
|---|---|
| `no_valid_candidates` | All candidates rejected |
| `single_point_consensus` | Exactly one candidate accepted |
| `conflict_between_top_candidates` | Accepted candidates contradict each other |
| `possible_echo_chamber` | ≥ 3 candidates share identical text, all scoring below 0.55 |

### Output — ValidationResult

```python
@dataclass(frozen=True)
class ValidationResult:
    ranked_candidates: list[ValidatedCandidate]
    winner_agent_id: str | None
    consensus_status: str
    consensus_summary: str
    global_risk_flags: list[str]
    trace_artifact: ValidationTraceArtifact | None = None      # filled by Layer 2
    governance_report: ValidationGovernanceReport | None = None # filled by Layer 3
```

---

## Layer 2 — LifetraValidationAdapter

Records the validation event as a compact, inspectable trace artifact.
Does **not** influence winner selection.

### What it builds

**Nodes** — one per object in the validation event:

| Node id | Kind | Contents |
|---|---|---|
| `task:prompt` | task prompt | preview, text hash |
| `candidate:<agent_id>` | candidate | accepted, score, preview, hash, risk flags, reasons |
| `validation:result` | result | winner, consensus status, global risk flags |

**Edges** — relations between nodes:

| Relation | Meaning |
|---|---|
| `evaluates` | task:prompt → candidate (every candidate) |
| `accepted` | candidate → validation:result (if accepted) |
| `rejected` | candidate → validation:result (if rejected) |
| `supports` | candidate → candidate (from CandidateAnswer.supports) |
| `contradicts` | candidate → candidate (from CandidateAnswer.contradicts) |
| `winner` | winning candidate → validation:result |

**Trajectory** — a Lifetra `TrajectoryState` capturing the event as an ordered
sequence of `StateTransition` steps, with a final `summary()` string.

### Output — ValidationTraceArtifact

```python
@dataclass(frozen=True)
class ValidationTraceArtifact:
    backend: str                    # "lifetra_py"
    trace_id: str                   # "lifetra:<16-char sha256>"
    node_count: int                 # == len(metadata["nodes"])
    edge_count: int                 # == len(metadata["edges"])
    winner_agent_id: str | None
    global_risk_flags: list[str]
    summary: str                    # Lifetra trajectory summary string
    metadata: dict[str, Any]        # nodes, edges, accepted/rejected ids, etc.
```

`trace_id` is deterministic: same task prompt + same agents + same outcome
always produces the same id, regardless of candidate order.

### Graceful degradation

If `lifetra_py` is not installed, `build_validation_trace()` returns `None`
and `ValidationResult.trace_artifact` stays `None`. The validator works normally.

---

## Layer 3 — ValidationGovernanceEngine

An advisory overlay that looks at **history across rounds** to detect
anomalies the base validator cannot see in a single round.

It does **not** change `winner_agent_id`. It adds a parallel `governed_winner_agent_id`
and a `review_required` signal that downstream systems can act on.

### What it tracks per round

- paraphrase clusters (token + shingle Jaccard similarity, no embeddings)
- agent reputation profiles with recency decay
- coalition alerts when pairs of agents repeatedly align
- quorum snapshot: how many trusted agents support the current winner
- escalation recommendations

### Constructor options

```python
ValidationGovernanceEngine(
    history_store=InMemoryValidationHistoryStore(),  # or JsonlValidationHistoryStore("path.jsonl")
    paraphrase_threshold=0.58,       # Jaccard threshold for "same idea"
    coalition_repeat_threshold=3,    # rounds before pair triggers coalition alert
    quorum_size=2,                   # minimum trusted supporters for quorum
    trusted_reputation_threshold=0.52,
    history_decay=0.82,              # how fast old rounds lose weight
)
```

### History stores

| Class | Use when |
|---|---|
| `InMemoryValidationHistoryStore` | Tests, single-process use |
| `JsonlValidationHistoryStore("path.jsonl")` | Persistent history across restarts |

### Reputation score

Each agent accumulates a score in `[0, 1]` based on weighted history:

```
reputation = 0.5
           + 0.30 × accepted_rate
           + 0.18 × winner_rate
           − 0.18 × conflict_rate
           − 0.15 × echo_rate
           − 0.24 × coalition_rate
```

Trust tiers:

| Tier | Score range |
|---|---|
| `trusted` | ≥ 0.75 |
| `watch` | 0.58 – 0.75 |
| `probing` | 0.42 – 0.58 |
| `untrusted` | < 0.42 |

### Governance flags

Appended on top of the base validator's `global_risk_flags`:

| Flag | Raised when |
|---|---|
| `semantic_paraphrase_cluster` | Suspicious similarity cluster found this round |
| `coalition_risk_detected` | At least one coalition alert present |
| `distributed_quorum_missing` | Winner lacks enough trusted support |
| `trusted_veto_present` | A trusted agent contradicted the winner |
| `low_trust_governed_winner` | Governed winner has reputation below threshold |
| `governed_winner_differs_from_base` | Governance would pick a different winner |

### review_required

Set to `True` when any of the following is true:

- there are escalation recommendations
- `governed_winner_differs_from_base` is flagged
- `trusted_veto_present` is flagged

When `True`, the round should not be treated as settled without human review.

---

## Using layers independently

Each layer is optional:

```python
# Layer 1 only — original behavior, no dependencies
validator = CollectiveAnswerValidator()

# Layer 1 + 2 — adds trace artifact, no history
validator = CollectiveAnswerValidator(trace_backend=LifetraValidationAdapter())

# Layer 1 + 3 — adds governance, no trace artifact
validator = CollectiveAnswerValidator(governance_engine=ValidationGovernanceEngine())

# All three layers
validator = CollectiveAnswerValidator(
    trace_backend=LifetraValidationAdapter(),
    governance_engine=ValidationGovernanceEngine(
        history_store=JsonlValidationHistoryStore("history.jsonl")
    ),
)
```

---

## Reading a result

```python
result = validator.validate(payload)

# Base decision — always present
result.winner_agent_id         # str | None
result.consensus_status        # "convergent" | "weak" | "conflicted" | "rejected"
result.global_risk_flags       # list[str]
result.ranked_candidates       # sorted by score desc

# Trace artifact — present when trace_backend was supplied
if result.trace_artifact:
    result.trace_artifact.trace_id
    result.trace_artifact.node_count
    result.trace_artifact.edge_count
    result.trace_artifact.metadata["edges"]   # full edge list
    result.trace_artifact.metadata["nodes"]   # full node list

# Governance report — present when governance_engine was supplied
if result.governance_report:
    result.governance_report.governed_winner_agent_id
    result.governance_report.review_required
    result.governance_report.governance_flags
    result.governance_report.escalation_recommendations
    result.governance_report.agent_profiles     # reputation per agent
    result.governance_report.coalition_alerts
    result.governance_report.paraphrase_clusters
    result.governance_report.distributed_consensus.quorum_reached
```

---

## Design principles

**The validator decides. Lifetra records. Governance inspects.**

- Scoring and acceptance logic lives only in `CollectiveAnswerValidator`.
- The trace adapter is post-decision and read-only with respect to the winner.
- The governance engine is advisory — it produces a parallel recommendation,
  never silently overwrites the base winner.
- All three layers are independently replaceable or removable.
- Validator import carries zero runtime dependency on the trace or governance stack.

---

## Current limits

- Paraphrase clustering is heuristic (Jaccard on tokens and shingles), not semantic.
- Score adjustments from governance are advisory; they do not feed back into the
  base validator's acceptance decision.
- Reputation memory is history-file based, not cryptographic or distributed.
- Quorum is a lightweight snapshot, not a Byzantine-fault-tolerant protocol.
- Coalition detection surfaces anomalies for review; it does not auto-quarantine agents.
