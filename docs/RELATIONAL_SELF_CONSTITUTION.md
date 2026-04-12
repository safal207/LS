# Relational Self Constitution (Phase 2.3.1 Foundation)

## Why
Relational Self already computes coherence and supports council action proposals.
The next differentiator is **normative identity governance**: explicit invariants that
must hold for the system to remain a coherent self.

## Constitution goals
1. Declare non-negotiable identity constraints.
2. Evaluate every council cycle against those constraints.
3. Emit machine-readable governance signals (`warn`, `block`, `escalate`).

## Initial rule set (v0)
- `min_coherence`: self coherence must remain above threshold.
- `max_contradiction_density`: contradictory strong edges should not dominate core graph.
- `alignment_floor`: average alignment over core nodes must stay above threshold.

## Runtime integration
- Add evaluator in `modules.council.self_constitution`.
- `RelationalCouncilEngine.self-preservation` invokes evaluator and returns
  `constitution` payload with per-rule status.
- If any `block` rule fails, self-preservation blocks action execution.

## MCP / observability (next)
- Add resource `self/constitution-status`.
- Add trend view over constitution violations by cycle.

## Acceptance criteria for this foundation PR
- Constitution evaluator exists with deterministic evaluation.
- Self-preservation returns constitution payload.
- Unit tests cover pass/fail and severity behavior.
