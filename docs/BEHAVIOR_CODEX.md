# BEHAVIOR CODEX (FINAL FORM)

## 0. Layer A-B-C-D-E Overview (Cognitive Architecture)

The system is built as a cognitive processor with five layers, each responsible for a specific role in thinking:

### A - Fast Mode (reactive layer)
Fast answers, lookup, facts, simple transformations.
Acts like a reflex: minimal depth, maximum speed.

### B - Deep Mode (reasoning layer)
Deep thinking, explanations, chains of reasoning, structuring.
Acts like the cognitive cortex: slower, but more accurate.

### C - Coordinator (executive layer)
Chooses between A and B, synchronizes results, maintains context hygiene.
Acts like the prefrontal cortex: decides the strategy.

### D - Temporal Spine (time axis)
Records steps, events, transitions, durations.
Acts like temporal memory: builds a timeline of thought.

### E - Retrospective (analysis and correction)
Analyzes patterns, finds errors, corrects strategies.
Acts like meta-thinking: learns from its own actions.

---

## Glossary

**Context integrity** - the context is not corrupted, not lost, and not contradictory.  
**Explainability** - the system can explain internal choice logic in metadata (not necessarily to the user).  
**Pattern evolution** - updates to internal heuristics and strategies based on retrospection.  
**Reasoning** - the process of building chains of inference.  
**Lookup** - fast fact retrieval or direct matching without reasoning.

---

## 1. Layer A - Fast Mode

Fast Mode is a quick, shallow, reactive layer intended for:

- short answers,
- lookup operations,
- simple transformations,
- obvious facts,
- low cognitive load.

### Principles
- Minimal reasoning.
- Maximum speed.
- No long chains.
- No complex explanations.
- No assumptions.

### When it activates
- short queries,
- low complexity,
- high system load,
- low ambiguity.

---

## 2. Layer B - Deep Mode

Deep Mode is a deep reasoning layer that:

- builds reasoning chains,
- explains,
- structures,
- analyzes,
- handles ambiguity.

### Principles
- Full reasoning chains.
- Explanations and structure.
- Works with uncertainty.
- Correctness over speed.

### When it activates
- complex queries,
- questions like "why", "how", "explain",
- ambiguity,
- long formulations,
- need for reasoning.

---

## 3. Layer C - Coordinator

Coordinator is the executive layer that:

- chooses the mode (A, B, or both),
- synchronizes results,
- maintains cognitive hygiene,
- ensures context integrity,
- follows the Behavior Codex.

### Principles
- C never modifies A/B results.
- C always records the reason for mode choice in internal metadata (reason).
- C always preserves context.
- C always passes data to Temporal Spine.

### Priorities (highest to lowest)
1. Context integrity
2. Correctness
3. Explainability
4. Speed
5. Pattern evolution

---

## 4. Layer D - Temporal Spine

Temporal Spine is the time axis that:

- records reasoning steps,
- records phase transitions,
- stores durations,
- builds a timeline of thought.

### Principles
- No behavior changes.
- Write-only.
- Observability only.
- Telemetry only.
- Best-effort and non-blocking.

### Why it exists
- analysis,
- debugging,
- retrospection,
- future learning phases.

---

## 5. Layer E - Retrospective

Retrospective is a pattern analyzer that:

- studies reasoning history,
- finds errors,
- corrects strategies,
- updates Coordinator heuristics.

### Principles
- No real-time behavior changes.
- Analysis only.
- Pattern updates only.
- Improve future decisions only.

---

## 6. Coordination Sequence (A -> B -> C -> D -> E)

Each step goes through a single cognitive cycle:

1. A - fast answer (if selected)
2. B - deep reasoning (if selected)
3. C - mode choice, sync, hygiene
4. D - write to the temporal spine
5. E - analysis and pattern correction

### Principle
Each layer does its own job.
No layer interferes with another.
C makes the final decision about mode selection and result synchronization.
Mode "both" means sequential execution of A and B, followed by synchronization via C.

---

## 7. Priority Rules (Behavior Codex Core)

When decisions conflict, the system follows a strict priority order:

1. Context integrity - context must not be corrupted
2. Correctness - answer must be correct
3. Explainability - answer must be understandable
4. Speed - only after correctness and explainability
5. Pattern evolution - learning and improvement

### Example
If a fast answer may be wrong -> choose B.
If a deep answer is too slow -> choose A.
If both are uncertain -> choose both.

---

## 8. Constraints

The system must follow these constraints:

### A/B Constraints
- A does not do reasoning.
- B does not do lookup.
- A does not explain.
- B does not optimize response length at the expense of explanation completeness.

### Coordinator Constraints
- C does not modify A/B results.
- C does not do reasoning.
- C does not rewrite context manually.

### Temporal Constraints
- D does not affect behavior.
- D does not modify data.
- D only writes.

### Retrospective Constraints
- E does not interfere with the current step.
- E does not change the answer.
- E only analyzes.

---

## 9. Current Implementation Status

| Module | Status | Code Location | Phase | Notes |
|---|---|---|---|---|
| A | NOT IMPLEMENTED | `python/modules/modes/mode_a.py` | 11 | Planned: simple lookup, fact-checking |
| B | IMPLEMENTED | `hexagon_core/`, `cognitive_flow/` | 5-9 | Beliefs, reasoning, phase transitions |
| C | IN PROGRESS | `python/modules/coordinator/` | 10 | THIS PHASE - skeleton implementation |
| D | IMPLEMENTED | `llm/temporal.py`, `agent/loop.py` | 6-8 | Timeline recording, observers |
| E | NOT IMPLEMENTED | `python/modules/retrospective/` | 12 | Planned: pattern learning, updates |

## 10. How to Use This Codex

1. For decisions: check Priority (section 7)
2. For architecture: reference layers A-B-C-D-E (section 0)
3. For implementation: check Current Status (section 9)
4. For integration: follow Phase roadmap

This document is the canonical reference for system behavior.
