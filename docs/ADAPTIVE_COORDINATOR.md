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

## Behavior

- Biases are clamped and combined.
- `decision.mode` is unchanged.
- `decision.confidence` is softly adjusted.

## Non-Goals

- No mode switching rules
- No policy enforcement
- No learning or persistence
