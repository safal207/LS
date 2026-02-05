# Orientation Center (Phase 13)

## Overview

The Orientation Center (O) is a lightweight, non-invasive layer that provides
an orientation signal to the rest of the system. It does not change behavior.

Phase 13 introduces the **Rhythm Engine** as the first signal generator for O.

## Responsibilities

- Compute an orientation signal based on system state metrics.
- Expose the rhythm phase (inhale / hold / exhale).
- Remain side-effect free.

## Non-Goals

- No policy enforcement.
- No mode switching.
- No behavior modification.
- No persistence.

## Outputs

Orientation Center returns:

```
{
  "rhythm_phase": "inhale" | "hold" | "exhale",
  "chaos_score": float,
  "harmony_score": float,
  "delta": float
}
```

## Phase 13 Status

Skeleton only. Provides a signal for future use in Coordinator (Phase 13+).
