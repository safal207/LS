# Coordinator Module Specification (Phase 10)

## Overview

The Coordinator (C) is the decision-making layer that:
1. Chooses between Mode A (fast) and Mode B (deep)
2. Synchronizes context between modes
3. Maintains cognitive hygiene
4. Ensures Codex compliance

## Interface

### 1. choose_mode(input_data, context, system_load)
Purpose: Determine which mode(s) to activate.
Input: User query, current context, system load (0-1)
Output: CoordinationDecision with mode and reasoning

Decision rules (v0.1):
- Simple input + low load -> Mode A
- Complex input OR explanation needed -> Mode B
- Default -> both (verify)

### 2. sync_context(mode_a_result, mode_b_result, context)
Purpose: Merge results from modes into context.
Guarantee: No data loss, context integrity maintained.

### 3. cleanup(context)
Purpose: Cognitive hygiene (remove noise, prevent cycles).
Effect: Returns cleaned context.

### 4. finalize(mode_result, context)
Purpose: Orchestrate full pipeline (sync + cleanup).
Effect: Returns finalized result and updated context.

## Integration with AgentLoop

```python
# In AgentLoop.step():
decision = coordinator.choose_mode(input, context)
result = execute_mode(decision.mode)
result, context = coordinator.finalize(result, context)
```

## Roadmap

- v0.1 (CURRENT): Skeleton with simple heuristics
- v0.2: Real decision logic using metrics
- v0.3: Adaptive heuristics, learning from retrospection

## See Also

- docs/BEHAVIOR_CODEX.md - Formal codex
- Phase 11: Mode A (Fast Mode)
- Phase 12: Retrospective (E)
