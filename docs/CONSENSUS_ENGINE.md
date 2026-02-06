# Multi-Agent Consensus Engine (Phase 20)

## Purpose
Provide a small, safe consensus adjustment derived from field metrics and
local mode selection to improve distributed agreement.

## Behavior
- Computes an adjustment in [-0.15, 0.15].
- Positive adjustment increases confidence in the chosen mode.
- Negative adjustment reduces confidence.
- Never overrides ModeDetector.
- Never forces a mode change.

## Safety
- Clamped values.
- No direct mode switching.
- No feedback loops.
- No persistence.

## Non-Goals
- No voting.
- No leader election.
- No global synchronization.
