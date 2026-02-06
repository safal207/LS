# Adaptive Coordinator (Phase 15)

## Overview

Phase 15 introduces soft adaptive biasing for Coordinator decisions.
It **does not change mode selection**, only adjusts decision confidence.

## Inputs

- `orientation` (weight, tendency)
- `trajectory_error` (from Trajectory Layer)

## Outputs

- `orientation_bias`
- `trajectory_bias`
- `adaptive_bias`
- `confidence_raw`
- `confidence_smoothed`

## Behavior

- Biases are clamped and combined.
- `decision.mode` is unchanged.
- `decision.confidence` is softly adjusted.

## Confidence Dynamics (Phase 15.1)

Coordinator applies temporal smoothing to decision confidence:

- Uses exponential smoothing with bounded step size.
- Exposes both `confidence_raw` and `confidence_smoothed`.
- Does not change mode selection.

## Meta-Adaptation (Phase 16)

Coordinator maintains simple aggregates of error and confidence and softly
adjusts its own adaptation parameters:

- `ConfidenceDynamics.alpha`
- `ConfidenceDynamics.max_delta`

This is non-invasive and does not change mode selection.

## Meta-Hygiene (Phase 16.1)

Coordinator applies a stabilizing layer that clamps or resets adaptation
parameters when anomalous spikes are detected. This prevents runaway
adaptation without changing mode selection.

## Non-Goals

- No mode switching rules
- No policy enforcement
- No learning or persistence
