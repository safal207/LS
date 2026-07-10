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

The first specimens reconstruct the real delivery history of `safal207/robys-coffee-house-demo`.

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

## Append-only snapshots

A later observation does not rewrite a historically valid trail. LS preserves the original snapshot and appends a new exact-head snapshot when the external state changes.

The Robys delivery sequence is represented by two complementary fixtures:

```text
PR #165 local CTA merge
  -> customer detects logo and catalog delivery tails
  -> historical open-tail fixture: RISK_DISCOVERED
  -> PR #173 delivers production-referenced wordmark
  -> PR #167 delivers pairing cardinality and source parity
  -> current closure fixture: MERGED
```

This separates two true statements that existed at different times:

- the delivery tails were genuinely open after the local CTA merge;
- both tails were later closed through independently reviewed exact-head changes.

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
- `fixtures/robys_pr_164_wordmark.json` — historical wordmark risk and review-regression specimen;
- `fixtures/robys_pr_165_open_delivery_tails.json` — historical open delivery-tail snapshot;
- `fixtures/robys_pr_167_closed_delivery_tails.json` — current exact-head closure snapshot through merged PR #173 and PR #167;
- `fixtures/robys_pr_164_levels.json` — three-level causal overlay;
- `fixtures/robys_pr_164_visual_benchmark_2026_07.json` — July 2026 visual benchmark;
- `tests/` — positive and mutation coverage.

## Run

```bash
python ls-conformance/causal_phase_trail/validate.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json

python ls-conformance/causal_phase_trail/validate.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_165_open_delivery_tails.json

python ls-conformance/causal_phase_trail/validate.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_167_closed_delivery_tails.json

python ls-conformance/causal_phase_trail/validate_levels.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_levels.json

python ls-conformance/causal_phase_trail/validate_visual_benchmark.py \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json \
  ls-conformance/causal_phase_trail/fixtures/robys_pr_164_visual_benchmark_2026_07.json

python -m unittest discover \
  -s ls-conformance/causal_phase_trail/tests -v
```

## Robys result

The original compatibility and delivery-tail fixtures remain historical evidence. They correctly preserve the states observed on their exact heads, including the regression to `RISK_DISCOVERED` and the two open customer-path tails.

The append-only closure fixture binds to Robys PR #167 exact head `e3f2a14696e9bc3ff5ab2f87829e5540019a39b9`. It records that the selected sequential route succeeded:

1. merged PR #173 delivered the production-referenced wordmark;
2. merged PR #167 delivered two pairing offers and enforced parity with Discover;
3. exact-head CodeRabbit and maintainer-attestation statuses were successful;
4. no unresolved blocker remains in the closure snapshot;
5. the reconstructed current phase is `MERGED`.
