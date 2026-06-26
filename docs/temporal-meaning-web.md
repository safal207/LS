# Temporal Meaning Web

## Status

Working design note for LS continuity architecture.

This document defines the **Temporal Meaning Web** as a layer for representing how meaning emerges across time, phases, transitions, individuals, systems, and environments.

It extends:

- `docs/continuity-coordinator.md`
- `docs/architecture-map.md`
- `docs/continuity-vocabulary.md`
- `schemas/temporal_meaning_edge.example.json`

The central question is:

> how do changes in an individual, a system, and an environment become one governed continuity story over time?

---

## 1. Core idea

Meaning is not stored only inside isolated events.

Meaning emerges from the relationship between:

- what changed;
- when it changed;
- which phase each participant was in;
- which forces were amplified or attenuated;
- whether the resulting action remained congruent with the wider whole;
- whether the transition should affect durable continuity or identity.

```text
individual phase
  <-> system phase
  <-> environment phase
  <-> temporal boundary
  <-> transition
  <-> meaning edge
  <-> continuity impact
```

The Temporal Meaning Web is a graph of **phase-aware, evidence-bound transitions**.

---

## 2. Why LS needs this layer

The existing LS identity chain already distinguishes:

```text
VerifiedEpisode
  -> TrackAggregationRecord
  -> IdentityProposalCandidate
  -> GovernanceDecision
  -> IdentityUpdateRecord
  -> IdentitySnapshot
```

The Temporal Meaning Web adds a question between episode and aggregation:

> what did this event mean in relation to the phase of the individual, the phase of the system, the phase of the environment, and the passage of time?

Two similar actions may carry different meanings when:

- one occurs during exploration and another during recovery;
- one uses fresh evidence and another uses stale evidence;
- one increases system coherence and another hides unresolved conflict;
- one preserves recovery capacity and another consumes it;
- one is authorized now and another only remembers prior authorization.

Without phase and transition context, aggregation may count similarity while missing meaning.

---

## 3. Three phase domains

### Individual phase

The state of the person, agent, or actor.

Examples:

- `exploration`
- `commitment`
- `execution`
- `verification`
- `reflection`
- `recovery`
- `recalibration`
- `closure`

### System phase

The lifecycle state of the wider technical or social system.

Examples:

- `initializing`
- `expanding`
- `converging`
- `executing`
- `degraded`
- `recovering`
- `revalidating`
- `stable`
- `closing`

### Environment phase

The state of the external context.

Examples:

- `unchanged`
- `constraint_shift`
- `permission_change`
- `repository_drift`
- `resource_pressure`
- `new_evidence`
- `external_failure`
- `opportunity_window`

---

## 4. Phase-aware loop

```text
CALIBRATE
-> EXPAND
-> COMMIT
-> EXECUTE
-> VERIFY
-> REFLECT
-> CONTINUE | RECALIBRATE | CLOSE | ESCALATE
```

The load-bearing transition is:

```text
EXPAND -> COMMIT
```

Expansion opens possibilities, evidence, risks, and interpretations.

Commitment converts that opening into a bounded next step with:

- a concrete action;
- supporting evidence or explicit assumptions;
- an expected observable result;
- a verification method;
- a reconsideration or stop condition.

A loop is healthy when each iteration creates a reality-based transition, not merely another turn.

---

## 5. Congruence gate

A transition should not be considered ready only because it is executable.

It should be evaluated across:

- **goal alignment** — does it advance the governed objective?
- **evidence alignment** — is it supported by current verified evidence?
- **system alignment** — does it preserve architecture, safety, compatibility, and other active workstreams?
- **temporal alignment** — is this still the right action now?
- **consequence alignment** — are the effects observable, bounded, and reversible where necessary?

Congruence is not proof that the full path is correct.

```text
congruence permits the step
reality validates the path
```

---

## 6. Temporal phase and three clocks

Long-running systems cross boundaries such as compaction, process restart, long pause, quota reset, repository drift, permission change, new evidence, or changed human intent.

At these boundaries, three independent clocks may diverge:

```yaml
temporal_state:
  memory_freshness: current | stale | unknown
  evidence_validity: valid | revalidation_required | invalid
  action_authority: authorized | expired | blocked
```

These values must not be inferred from one another.

- Memory may survive while evidence becomes stale.
- Evidence may remain true while authority expires.
- A goal may remain active while its previous committed step becomes incongruent.

Therefore:

> persisted state is not automatically actionable state.

A safe resume path is:

```text
RESTORE MEMORY
-> REVALIDATE EVIDENCE
-> RECOMPUTE CONGRUENCE
-> RENEW ACTION AUTHORITY
-> CONTINUE | RECALIBRATE | BLOCK
```

---

## 7. Observer layer

A long-running loop needs a position from which it can observe its own behavior.

The observer is not another executor. It records how the loop is moving.

```yaml
observer_state:
  current_phase: verify
  dominant_driver: evidence | urgency | habit | recovery
  repeated_pattern: "third retry with unchanged hypothesis"
  unresolved_dissonance:
    - "local tests pass but compatibility is unverified"
  progress_signal: none | local | goal_level
```

The observer should detect:

- repeated action without a changed hypothesis;
- synthetic progress;
- hidden uncertainty;
- attachment to a stale plan;
- premature closure;
- local success with system-level damage;
- confidence unsupported by external verification.

Observation should remain non-punitive. For a human-centered system, it supports awareness with dignity. For an agent system, it supports truthful state reporting without invented continuity.

---

## 8. Integrity preservation

A loop should not achieve a local objective by degrading its capacity to continue safely and truthfully.

For human participants, this includes dignity, sustainable effort, and recovery capacity.

For agents and technical systems, it includes state integrity, safety constraints, recovery capacity, and explicit uncertainty.

```yaml
integrity_preservation:
  preserve_identity_continuity: true
  preserve_state_integrity: true
  preserve_safety_constraints: true
  preserve_recovery_capacity: true
  surface_uncertainty: true
```

Core principle:

> the path should preserve the integrity of the actor that is walking it.

---

## 9. Loops as force transformers

A loop is not neutral. Every iteration amplifies some forces and attenuates others.

```yaml
force_delta:
  amplify:
    - verified_knowledge
    - implementation_reliability
    - system_coherence
  attenuate:
    - uncertainty
    - repeated_error
  protect:
    - safety
    - state_integrity
    - recovery_capacity
```

A good loop does not always make action stronger. Sometimes its highest function is to reduce the force that keeps producing the wrong action.

The review question is:

> did this iteration make the whole system stronger, or did one metric improve by consuming the rest?

---

## 10. TemporalMeaningEdge

A `TemporalMeaningEdge` connects phase-aware records and explains why their relationship matters.

Candidate fields:

- `edge_id`
- `source_refs`
- `individual_phase`
- `system_phase`
- `environment_phase`
- `transition_class`
- `meaning_statement`
- `evidence_refs`
- `congruence_state`
- `observer_state`
- `force_delta`
- `temporal_state`
- `continuity_impact`
- `identity_proposal_eligible`
- `governance_requirements`

A meaning edge must not fabricate causality. It may express a verified relationship, supported interpretation, unresolved hypothesis, contradiction, counterevidence, phase transition, continuity break, or continuity restoration.

---

## 11. Relationship to ContinuityCoordinator

The Temporal Meaning Web does not replace `ContinuityCoordinator`. It enriches coordinator input.

```text
VerifiedEpisode
  -> TemporalMeaningEdge
  -> phase-aware continuity interpretation
  -> ContinuityCoordinator
  -> TrackAggregationRecord / counterevidence / confidence shaping
  -> IdentityProposalCandidate
  -> governance
```

The coordinator may use meaning edges to determine:

- whether similar events occurred in the same or different phases;
- whether repetition represents mastery, recovery, compulsion, or drift;
- whether the environment changed between episodes;
- whether evidence and authority were valid at action time;
- which forces the repeated loop strengthened;
- whether a transition increased or reduced system coherence;
- whether the pattern is eligible to influence identity.

A meaning edge is still not identity authority.

---

## 12. Continuity impact classes

- `no_durable_impact`
- `episode_context_only`
- `track_signal`
- `counterevidence_signal`
- `recalibration_required`
- `identity_proposal_candidate`
- `continuity_break`
- `continuity_restoration`

---

## 13. Required invariants

1. A phase label must not substitute for evidence.
2. A remembered state must not imply current authority.
3. Congruence must not be inferred from internal consistency alone.
4. External reality must remain able to contradict the current interpretation.
5. The observer must record uncertainty rather than invent missing continuity.
6. Force amplification must be evaluated at system level, not only local metric level.
7. Integrity preservation must remain active during success, failure, and recovery.
8. A `TemporalMeaningEdge` must preserve source references and temporal provenance.
9. A meaning edge may influence aggregation but must not directly mutate identity.
10. Counterevidence must be able to weaken, block, or reverse a meaning interpretation.

---

## 14. Example

```text
An agent commits to a repository migration.

At commit time:
  individual phase = commitment
  system phase = stable
  environment phase = unchanged
  evidence validity = valid
  action authority = authorized

After a long pause:
  memory freshness = current
  repository state = drifted
  evidence validity = revalidation_required
  action authority = expired

The agent restores memory but does not immediately continue.
It revalidates the repository, recomputes congruence,
and discovers that the old migration step would now break compatibility.

The resulting meaning is not "the agent failed to continue."
The meaning is "the system preserved continuity by refusing stale action."

Force delta:
  amplified = awareness, safety, system coherence
  attenuated = urgency, false certainty

Continuity impact:
  track_signal for judgment / recovery
  no direct identity update
```

---

## 15. Summary

```text
individual
  <-> system
  <-> environment
  <-> time
  <-> phase
  <-> transition
  <-> meaning
  <-> continuity
```

Core principle:

> Meaning is not only what is remembered. Meaning is what preserves truthful continuity through change.

Operationally:

> A healthy loop observes what it amplifies, preserves actor integrity, revalidates itself across time, and continues only through a reality-based congruent step.

---

## 16. Related discussions

- Codex long-running goal phases and temporal revalidation:
  - https://github.com/openai/codex/issues/20958#issuecomment-4807928710
  - https://github.com/openai/codex/issues/20958#issuecomment-4807978083
- Claude Code compact/session lifecycle hooks:
  - https://github.com/anthropics/claude-code/issues/47023
