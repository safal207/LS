# Orientation Organs (Phase 13.2)

## Overview

Phase 13.2 adds modular orientation organs that compute independent signals.
These signals are used by the Rhythm Engine but do not change behavior.

## Organs

### Metabolic Diversity
- Input: history stats (paths, entropy)
- Output: diversity_score (0-1)

### Belief Aging
- Input: beliefs with age/support
- Output: stability_score (0-1)

### Temporal Causality
- Input: short-term vs long-term metrics
- Output: contradiction_rate (0-1)

### Cognitive Immunity
- Input: drift/anomaly/bias signals
- Output: drift_pressure (0-1)

### Conviction Regulator
- Input: support/diversity/conflict/age
- Output: confidence_budget (0-1)

## Notes

All organs are best-effort and side-effect free.
No organ modifies behavior directly.
