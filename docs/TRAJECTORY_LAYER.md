# Trajectory Layer (Phase 14.1)

## Purpose

The Trajectory Layer tracks sequences of decisions, contexts, and outcomes.
It provides a simple trajectory error metric based on recorded outcomes.

## Responsibilities

- Record decisions with context
- Record outcomes for the last decision
- Compute trajectory_error (ratio of unsuccessful outcomes)

## Non-Goals

- No learning
- No behavior changes
- No policy enforcement
- No persistence beyond in-memory history

## API

```
record_decision(decision: str, context: dict)
record_outcome(outcome: dict)
compute_trajectory_error() -> float
```

## Notes

- Uses outcome["success"] == False as error signal
- If no outcomes are recorded, error is 0.0
