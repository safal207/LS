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

## Causal levels

The exact-head level overlay assigns every trail node to `INDIVIDUAL`, `SYSTEM`, or `ENVIRONMENT` and validates the closed feedback loop:

```text
INDIVIDUAL -> SYSTEM -> ENVIRONMENT -> SYSTEM -> INDIVIDUAL
```

See `LEVEL_MODEL.md`.

## Time-scoped visual benchmark axis

`VBA-001` compares exact-head interface evidence with current external UI/UX references for a named month or year:

```text
our interface evidence
  + normative guidance
  + current design-system guidance
  + current trend/exemplar feed
  -> criterion gaps
  -> ADOPT / EXPERIMENT / DEFER / REJECT
```

The visual axis is deliberately separate from the causal levels. It answers whether a route is visually competitive now, while the levels answer where causes and constraints live.

Fail-closed rules include:

- every assessment binds both interface evidence and external source evidence;
- normative criteria require a normative source;
- trend-only evidence cannot directly justify `ADOPT`;
- every `EXPERIMENT` requires a guard;
- fast-moving sources expire quickly;
- scores and largest gaps are recomputed;
- the benchmark is always `ADVISORY_ONLY` and never grants merge authority.

The July 2026 Roby's fixture preserves the distinctive wordmark, proposes guarded experiments in expressive motion and tactile editorial imagery, rejects novelty navigation, and identifies product storytelling as the largest visual gap.

See `VISUAL_BENCHMARK_MODEL.md`.

## Files

- `causal-phase-trail.schema.json` — closed serialized trail shape;
- `validate.py` — deterministic trail validator;
- `causal-level-overlay.schema.json` — closed causal-level overlay shape;
- `validate_levels.py` — deterministic level validator;
- `visual-benchmark-axis.schema.json` — closed time-scoped benchmark shape;
- `validate_visual_benchmark.py` — deterministic benchmark validator;
- `fixtures/robys_pr_164_wordmark.json` — real CPT-001 specimen;
- `fixtures/robys_pr_164_levels.json` — three-level causal overlay;
- `fixtures/robys_pr_164_visual_benchmark_2026_07.json` — July 2026 visual benchmark;
- `tests/` — positive and mutation coverage.

## Run

```bash
python ls-conformance/causal_phase_trail/validate.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json

python ls-conformance/causal_phase_trail/validate_levels.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_levels.json

python ls-conformance/causal_phase_trail/validate_visual_benchmark.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_visual_benchmark_2026_07.json

python -m unittest discover \
  -s ls-conformance/causal_phase_trail/tests -v
```

## Current PR #164 result captured by the specimen

The compatibility fallback route reduced the original generated-content risk and forced exact-head visual evidence to be rebound. However, fresh current-head Qodo and CodeRabbit findings later introduced unresolved blockers, while the AI review contract remained red. The honest current phase is therefore `RISK_DISCOVERED`, not `MERGE_READY`.
