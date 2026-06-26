# Temporal Meaning Web — External Discussion Trail

## Status

Active ecosystem discussion record for the LS Temporal Meaning Web and phase-aware continuity contracts.

Last updated: 2026-06-26

This document preserves the external discussion trail around a shared architectural distinction:

```text
memory
!= evidence
!= authority
!= permission to continue
```

It records where the idea was proposed, how it was adapted to each project, what was published, and which follow-up tasks remain.

---

## 1. Canonical LS sources

- [`docs/temporal-meaning-web.md`](temporal-meaning-web.md)
- [`schemas/temporal_meaning_edge.schema.json`](../schemas/temporal_meaning_edge.schema.json)
- [`schemas/temporal_meaning_edge.example.json`](../schemas/temporal_meaning_edge.example.json)
- [`python/tests/test_temporal_meaning_edge.py`](../python/tests/test_temporal_meaning_edge.py)
- [`python/tests/test_temporal_meaning_restoration.py`](../python/tests/test_temporal_meaning_restoration.py)
- Implementation tracker: [LS issue #758](https://github.com/safal207/LS/issues/758)
- Continuity-restoration PR: [LS PR #759](https://github.com/safal207/LS/pull/759)

---

## 2. Ecosystem map

| Project | Discussion target | LS contribution | Publication status |
| --- | --- | --- | --- |
| OpenAI Codex | Long-running goals and phase-aware continuation | Explicit phases, congruence gate, observer state, temporal revalidation, action authority | Published |
| Claude Code | Compact/session lifecycle hooks | Memory freshness, evidence validity, and action authority as separate clocks | Draft prepared; publication not verified |
| Microsoft AutoGen | Mission Keeper / goal integrity | Mission fidelity plus phase-aware continuation validity and continuity restoration | User confirmed manual publication; exact comment URL not captured |
| CrewAI | Pre-tool-call `GuardrailProvider` | Time-bound and phase-bound authorization decisions with revalidation boundaries | Published |
| LangGraph | Cancellation and missing streamed checkpoint state | Persist partial visible state without treating it as completed or safe-to-resume state | Published |

---

## 3. OpenAI Codex

### Discussion

- https://github.com/openai/codex/issues/20958#issuecomment-4807928710
- https://github.com/openai/codex/issues/20958#issuecomment-4807978083

### Contribution

The discussion introduced a phase-aware continuation model:

```text
CALIBRATE
-> EXPAND
-> COMMIT
-> EXECUTE
-> VERIFY
-> REFLECT
-> CONTINUE | RECALIBRATE | CLOSE | ESCALATE
```

It also separated three temporal states:

```yaml
temporal_state:
  memory_freshness: current | stale | unknown
  evidence_validity: valid | revalidation_required | invalid
  action_authority: authorized | expired | blocked
```

### Follow-up tasks

- [ ] Monitor replies and references to phase-aware continuation.
- [ ] Compare Codex lifecycle terminology with the LS schema vocabulary.
- [ ] Prepare a compact conformance fixture for resume after repository drift.
- [ ] Track whether terminal-state reconciliation becomes available in public APIs.

---

## 4. Claude Code

### Discussion target

- https://github.com/anthropics/claude-code/issues/47023

### Contribution prepared

The proposal extends compact/session hooks with explicit lifecycle state:

```text
PERSIST MEMORY
-> RESTORE MEMORY
-> REVALIDATE EVIDENCE
-> RECOMPUTE CONGRUENCE
-> RENEW ACTION AUTHORITY
-> CONTINUE | RECALIBRATE | BLOCK
```

The connector returned `403 Resource not accessible by integration`, so publication was not verified from LS tooling.

### Follow-up tasks

- [ ] Confirm whether the prepared message was posted manually.
- [ ] Capture the exact comment URL if published.
- [ ] Map Claude Code compact/session events to `memory_freshness`, `evidence_validity`, and `action_authority`.
- [ ] Draft a lifecycle-hook payload fixture compatible with the Temporal Meaning Edge contract.

---

## 5. Microsoft AutoGen

### Discussion target

- https://github.com/microsoft/autogen/issues/7487

### Contribution

The Mission Keeper concept was extended from semantic goal fidelity to phase-aware continuation validity.

Core distinction:

```text
goal alignment
!= valid evidence
!= current authority
!= permission to take the next step now
```

Proposed Mission Keeper output:

```yaml
mission_keeper_state:
  logical_phase: calibrate | expand | commit | execute | verify | reflect
  goal_alignment: aligned | drifting | contradicted
  memory_freshness: current | stale | unknown
  evidence_validity: valid | revalidation_required | invalid
  action_authority: authorized | expired | blocked
  decision: allow | revalidate | recalibrate | block
  transition_reason: ...
```

The user confirmed manual publication, but the exact comment URL is not yet recorded here.

### Follow-up tasks

- [ ] Capture the exact AutoGen comment URL.
- [ ] Monitor replies from maintainers and participants.
- [ ] Compare Mission Keeper output with `TemporalMeaningEdge` fields.
- [ ] Design an AutoGen adapter that emits an inspectable decision record without executing tasks.
- [ ] Add a multi-agent goal-drift plus repository-drift conformance fixture.

---

## 6. CrewAI

### Published discussion

- https://github.com/crewAIInc/crewAI/issues/4877#issuecomment-4808449132

### Contribution

A `GuardrailProvider` allow decision should be phase-bound and time-bound rather than inherited for the whole crew run.

Candidate optional fields:

```python
phase: str | None
valid_until: str | None
revalidate_on: list[str]
decision: str  # allow | revalidate | block
```

Candidate revalidation boundaries:

- session resume;
- shared-state change;
- permission change;
- human-intent change;
- prior tool failure;
- agent handoff.

### Follow-up tasks

- [ ] Monitor responses to the published comment.
- [ ] Draft a CrewAI-compatible provider example using LS temporal states.
- [ ] Add accept/reject fixtures for expired authorization after agent handoff.
- [ ] Compare `BeforeToolCallHook` context with required LS provenance fields.
- [ ] Preserve compatibility with providers that only return `allow` and `reason`.

---

## 7. LangGraph

### Published discussion

- https://github.com/langchain-ai/langgraph/issues/5672#issuecomment-4808573509

### Contribution

A persisted partial state must remain distinguishable from a completed, safe-to-resume checkpoint.

Proposed lifecycle marker:

```yaml
checkpoint_state:
  completion: complete | partial | interrupted
  terminal_state_known: true | false
  resume_policy: continue | reconcile | branch | block
```

Core rule:

> Persisted state is not automatically completed or safe-to-resume state.

Proposed flow:

```text
persist visible partial state
-> mark interruption
-> reconcile terminal / branch state
-> continue | branch | block
```

### Follow-up tasks

- [ ] Monitor maintainer response and related frontend/backend findings.
- [ ] Add a LangGraph-style interrupted checkpoint fixture to LS.
- [ ] Model branch ancestry separately from transition completion.
- [ ] Add a reject vector where an interrupted node is resumed as completed.
- [ ] Add an accept vector for explicit branch reconciliation and continuity restoration.

---

## 8. Cross-project tasks

### Portable conformance pack

- [ ] Create `ls-conformance/phase_aware_resume/`.
- [ ] Add accepted vectors for valid continuation and explicit continuity restoration.
- [ ] Add rejected vectors for stale evidence, expired authority, unknown terminal state, and silent branch inheritance.
- [ ] Add a minimal schema that frameworks can adopt without importing the full LS architecture.

### Vocabulary alignment

- [ ] Compare project terms: `checkpoint`, `compact`, `session`, `mission`, `guardrail`, `authority`, `branch`, and `resume`.
- [ ] Define a stable LS crosswalk table.
- [ ] Keep memory, evidence, authority, completion, and continuity as independent dimensions.

### Evidence and monitoring

- [ ] Record replies, maintainer decisions, and linked PRs in this document.
- [ ] Store exact comment links rather than only issue links.
- [ ] Separate confirmed publication from prepared drafts.
- [ ] Add dates for meaningful external responses.

### Implementation path

- [ ] Feed validated `TemporalMeaningEdge` records into `ContinuityCoordinator`.
- [ ] Add framework-specific adapters only after the portable contract stabilizes.
- [ ] Keep external adapters incapable of directly mutating identity state.
- [ ] Require source provenance and temporal provenance for every imported ecosystem signal.

---

## 9. Shared ecosystem thesis

Across coding agents, multi-agent frameworks, guardrails, and graph runtimes, the same failure boundary appears:

```text
state can survive
while evidence expires
while authority changes
while the environment moves
```

Therefore:

> Long-running agents should not continue merely because state was persisted. They should continue only after the next transition is revalidated against current evidence, current authority, current phase, and current reality.

This discussion trail is evidence of convergence across different agent architectures, not evidence that any external project has adopted the LS model.