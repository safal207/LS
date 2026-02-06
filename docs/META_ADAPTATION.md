# Meta-Adaptation (Phase 16)

## Purpose

Allow Coordinator to softly adjust its own adaptation parameters over time
based on observed trajectory_error and confidence.

## Inputs

- `trajectory_error` (from Trajectory Layer)
- `confidence_smoothed` (from Confidence Dynamics)

## Outputs

Updated internal parameters:

- `ConfidenceDynamics.alpha`
- `ConfidenceDynamics.max_delta`
- (future) AdaptiveBias coefficients

## Behavior (Skeleton)

- Maintains running averages:
  - `avg_trajectory_error`
  - `avg_confidence`
- After a minimum number of updates:
  - High `avg_trajectory_error` -> decrease `max_delta`
  - Low `avg_confidence` -> increase `alpha`

## Non-Goals

- No mode switching
- No policy learning
- No persistence beyond in-memory state
- No opaque ML models
