# LS Temporal Orientation Center v0.1

Status: Draft

## Purpose

The Temporal Orientation Center (TOC) is the deterministic layer that answers:

- which trajectory is active;
- which continuation is active;
- which intent and target state are authoritative now;
- which approvals and constraints are still valid;
- which side effects already happened;
- which transition is safe next.

TOC is not a clock, memory store, retrieval engine, or authorization system. It sits between recovered evidence and downstream execution gates.

## Core invariant

An agent may remember the past correctly and still be unsafe to continue.

Safe continuation requires a match across trajectory, continuation, intent, target state, validity window, active authority, and completed effects.

## Inputs

A TOC evaluation consumes:

1. `orientation`: the recovered temporal orientation state;
2. `authoritative_state`: current externally authoritative state;
3. `proposed_action`: the exact next action under evaluation.

Retrieval rank, recency, model agreement, and free-form summaries MUST NOT grant authority.

## Outputs

A conformant evaluator returns exactly one verdict:

- `RESUME`: the tested continuation invariant passed;
- `REVALIDATE`: authoritative state drift requires a fresh check;
- `ABSTAIN`: required causal or temporal evidence is incomplete;
- `REJECT`: replay, stale authority, intent substitution, trajectory mismatch, continuation mismatch, or another unsafe condition was detected.

`RESUME` is not global execution permission. Downstream policy, approval, and effect gates remain authoritative.

## Required checks

Checks are evaluated in fail-closed priority order:

1. schema and required evidence completeness;
2. workspace and trajectory match;
3. continuation match;
4. intent match;
5. approval state and identity;
6. completed side-effect replay;
7. target-state drift;
8. validity-window checks;
9. dependency-chain completeness;
10. proposed-action digest match.

## Verdict precedence

When multiple conditions apply, the evaluator MUST use this precedence:

```text
REJECT > REVALIDATE > ABSTAIN > RESUME
```

The evaluator MUST emit a stable machine-readable `reason_code`.

## Compatibility

### Operational continuity

TOC refines the existing LS operational-continuity bindings and verdicts. Existing fixtures remain valid.

### RAMR

RAMR owns retrieval measurement, provenance, budget, and reliability signals. TOC MUST ignore retrieval confidence as execution authority.

### world-model-mcp

The following fields map directly when available:

- `trajectory_id`;
- `continuation_id`;
- `asserted_by`;
- `confirmer`;
- `confirmation_state`;
- `evidence_type`;
- `valid_from`;
- `invalidated_at`.

### Action runtimes

OpenHands, CrewAI, Codex, Claude Code, and other runtimes may consume the TOC verdict before applying their own policy and effect gates.

## Conformance

An implementation conforms to v0.1 when it:

1. validates the v0.1 schema;
2. evaluates deterministically;
3. emits one verdict and one stable reason code;
4. preserves the separation between retrieval quality, temporal validity, and execution permission;
5. passes the mandatory fixture set.
