# Collective Answer Validator

## Why multi-agent coordination still needs validation

In a multi-agent network each agent produces a candidate answer independently,
drawing on its own reasoning, memory, and context.  Shared memory improves
information flow but does not guarantee that the answer that surfaces to the top
is the *best* one — only that it was produced by some agent.

Without a validation layer the selection of a final answer depends entirely on
which agent happened to respond last, which one was most confident, or which one
repeated itself most often.  None of those criteria reliably correlates with
correctness, relevance, or safety.

## Shared memory vs. validated consensus

| Shared memory | Validated consensus |
|---|---|
| Propagates facts between agents | Evaluates candidate answers against quality criteria |
| Speeds up coordination | Ranks, filters, and explains selection |
| Does not distinguish good from bad signals | Rejects weak, contradictory, or high-risk outputs |
| Passive — stores what agents write | Active — decides what the network returns |

Shared memory is infrastructure.  Validated consensus is a quality gate.

## Why unvalidated consensus collapses

Three failure modes arise when candidate answers are accepted without scoring:

**Noise amplification.**  If several agents produce similar but subtly wrong
answers, a simple majority or "last writer wins" rule will promote the wrong
answer.  There is no mechanism to notice that every candidate shares the same
hallucination.

**Collusive reinforcement (echo chamber).**  When agents read each other's
outputs via shared memory and then regenerate nearly identical text, the
apparent "agreement" is not evidence of correctness — it is evidence of copying.
A validator that detects near-duplicate low-quality answers and flags
`possible_echo_chamber` breaks this loop.

**Contradiction blindness.**  Two well-scoring candidates can hold mutually
exclusive positions.  Without explicit contradiction tracking the system silently
picks one and discards the other, giving the caller no indication that the
network was in conflict.

## Module overview

`ls.cognition.collective_answer_validator` provides:

- **`CandidateAnswer`** — one agent's answer with quality signals pre-attached.
- **`ValidationInput`** — the task prompt plus all candidate answers.
- **`ValidatedCandidate`** — scoring result for one candidate: accepted/rejected,
  numeric score, human-readable reasons, and risk flags.
- **`ValidationResult`** — ranked list of validated candidates, a winner (or
  `None`), a consensus status string, a plain-language summary, and global risk
  flags.
- **`CollectiveAnswerValidator`** — the validator class with a single `validate`
  method.

### Scoring formula

```
score = 0.4 * relevance
      + 0.3 * thread_relevance
      + 0.1 * min(len(supports), 3) / 3
      - 0.2 * hallucination_risk
      - 0.1 * min(len(contradicts), 3) / 3
```

Score is clamped to `[0.0, 1.0]`.

### Acceptance criteria

A candidate is accepted only when **all four** conditions hold:

- `score >= 0.45`
- `relevance >= 0.30`
- `thread_relevance >= 0.30`
- `hallucination_risk <= 0.65`
- answer text is not empty

### Consensus status

| Status | Meaning |
|---|---|
| `convergent` | Two or more accepted candidates with close scores and no cross-contradictions |
| `weak` | Exactly one accepted candidate |
| `conflicted` | Accepted candidates contradict each other |
| `rejected` | No candidates met acceptance criteria |

### Risk flags

**Candidate-level**

| Flag | Trigger |
|---|---|
| `empty_answer` | `answer_text` is blank |
| `low_relevance` | `relevance < 0.30` |
| `low_thread_relevance` | `thread_relevance < 0.30` |
| `high_hallucination_risk` | `hallucination_risk > 0.65` |
| `contradiction_pressure` | `contradicts` list is non-empty |

**Global**

| Flag | Trigger |
|---|---|
| `no_valid_candidates` | No candidates accepted |
| `single_point_consensus` | Only one accepted candidate |
| `conflict_between_top_candidates` | Cross-contradictions among accepted set |
| `possible_echo_chamber` | 3+ candidates share identical normalised text and all score below 0.55 |

## MVP scope and limitations

This implementation is **deterministic** and requires **no external
dependencies, embeddings, or machine learning**.  Quality signals
(`relevance`, `thread_relevance`, `hallucination_risk`) are supplied by the
caller — typically the agent that generated the candidate or a lightweight
pre-scoring step.

Current limitations:

- The echo-chamber heuristic uses exact string matching after normalisation.
  Near-paraphrase detection would require embeddings.
- Scores are not calibrated against ground-truth data; thresholds are
  conservative defaults.
- The validator does not yet integrate into `AgentLoop`; it is designed as a
  standalone gate that can be called after candidate generation and before final
  answer selection.

## Integration note

The intended call site is between shared-memory candidate generation and final
answer selection in the multi-agent runtime:

```
shared memory → candidate generation → CollectiveAnswerValidator.validate() → final answer
```

Wire it in by passing all `CandidateAnswer` objects collected from the agent
round into a `ValidationInput` and using `ValidationResult.winner_agent_id` to
select the answer to return.
