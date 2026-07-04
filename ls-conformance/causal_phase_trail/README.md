# Causal Phase Trail V0

`CPT-001` records why a governed system changed phase, not merely which events happened first.

```text
observation
  -> causal diagnosis
  -> phase identification
  -> route comparison
  -> evidence-backed selection
  -> guarded transition
  -> durable trail
```

The first specimen reconstructs the real history of `safal207/robys-coffee-house-demo#164`.

## Boundary

A causal phase trail is evidence memory. It does not approve a pull request, authorize merge, execute a side effect, or turn an agent observation into truth by itself.

## Relations

The contract distinguishes:

- `PRECEDED`: temporal order only;
- `CAUSED`: an explicit explanatory claim;
- `DETECTED`: an observer or gate surfaced a condition;
- `BLOCKED`: a condition prevented a legal transition;
- `RESOLVED`: an action removed a named risk;
- `INVALIDATED`: a new state made exact-head evidence stale;
- `CONFIRMED`: evidence supported a claim on the bound head;
- `ENABLED`: satisfied guards made a transition legal;
- `REJECTED`: a route was considered and not selected.

A detector is not automatically a cause. The trail separately records detector, immediate cause, root cause, amplifying condition, and corrective action.

## Two clocks

Every node has:

- `eventTime`: when the represented condition or action existed;
- `observedAt`: when the trail learned or recorded it.

This allows the trail to answer both:

- what was believed at head X;
- what is now known about head X.

## Space

Nodes reference explicit spaces such as repository, pull request, artifact, component, surface, viewport, browser capability, agent, gate, and evidence object. Causes therefore remain local instead of being attributed to an entire feature or repository.

## Phases

V0 supports:

`IDEA`, `CANDIDATE`, `UNSTABLE`, `UNDER_REVIEW`, `RISK_DISCOVERED`, `CORRECTED`, `EVIDENCE_ACCUMULATING`, `STABLE`, `MERGE_READY`, and `MERGED`.

Each phase entry contains named guards and evidence references. A fresh binding blocker may regress a trail from a later phase back to `RISK_DISCOVERED`. This is intentional: green checks are evidence, not immunity from later findings.

## Route score

Each route preserves six components on a 0-5 scale:

```text
score = riskReduction
      + evidenceConfidence
      + reversibility
      - implementationCost
      - scopeExpansion
      - staleEvidenceCost
```

The score is advisory. The selected route must also contain a human-readable explanation and may not be selected from the number alone.

## Files

- `causal-phase-trail.schema.json` — closed serialized shape;
- `validate.py` — deterministic semantic validator;
- `fixtures/robys_pr_164_wordmark.json` — real CPT-001 specimen;
- `tests/test_causal_phase_trail.py` — positive and mutation coverage.

## Run

```bash
python ls-conformance/causal_phase_trail/validate.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json

python -m unittest discover \
  -s ls-conformance/causal_phase_trail/tests -v
```

## Current PR #164 result captured by the specimen

The compatibility fallback route reduced the original generated-content risk and forced exact-head visual evidence to be rebound. However, fresh current-head Qodo and CodeRabbit findings later introduced unresolved blockers, while the AI review contract remained red. The honest current phase is therefore `RISK_DISCOVERED`, not `MERGE_READY`.
