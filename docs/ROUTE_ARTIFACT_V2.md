# Route Artifact v2

Route Artifact v2 is the first narrow contract for the **Verified Route Network**.
It records a reusable problem-solving route without binding that route forever to
one model provider.

The core rule is:

> Models are replaceable. A route is promoted only when its useful effect is reproducible.

## Boundary

A route artifact is evidence memory. It does not authorize merge, deployment,
execution, memory writes, or any other protected side effect. Authorization
remains the responsibility of the appropriate evidence and action gates.

## Verification tiers

### T0 — deterministic replay

T0 requires:

- an exact 40-character Git HEAD;
- sandbox execution;
- an executable replay command;
- matching expected and observed exit codes;
- passing deterministic assertions;
- an evidence digest.

Only T0 may contribute to `confirmed_effectiveness`, route promotion, or a
training/distillation corpus.

### T1 — artifact-attested

T1 requires inspectable artifacts and explicit human sign-off, but it does not
claim deterministic replay. T1 may be stored as experimental evidence, but it
cannot contribute to confirmed effectiveness or training eligibility.

The first seed route references the live review experiments in:

- `safal207/LS#770`;
- `safal207/robys-coffee-house-demo#153`.

Those runs remain T1 until replayable evidence and outcomes exist.

### T2 — narrative-only

T2 has no reproducible artifact. It is rejected from the canonical store. The
verifier may parse it only in rejection-audit mode so the rejection reason can
be recorded without promoting the narrative into route evidence.

## Immutable versions and lineage

Each route version has a canonical SHA-256 digest. The digest covers the whole
artifact with `integrity.content_digest` normalized to `null` before hashing.

A newer immutable object may declare:

```json
{
  "lineage": {
    "supersedes": ["high-risk-code-review@1.0.0"]
  }
}
```

The older object is never edited. `superseded_by` is a derived registry
projection, not a field written back into the prior content-addressed object.
Missing references and direct or multi-hop supersession cycles fail closed.

## Route stages

Stages refer to roles and capability classes, not provider brands. Dependencies
must reference existing earlier stages. This yields a deterministic topological
order and rejects missing dependencies or cycles.

## Registry statuses

- `draft` — incomplete contract work;
- `experimental` — valid artifact with insufficient promotion evidence;
- `candidate` — automated quantitative gates pass;
- `validated` — candidate gates plus required maintainer approval pass;
- `deprecated` — still historically valid but obsolete;
- `revoked` — unsafe or invalid and must not be recommended.

The initial promotion policy uses configurable thresholds. The sample policy
requires at least 20 T0 runs, two repositories, two task variants, one sealed
honeypot, no unresolved critical false negatives, confidence intervals, and
maintainer approval. These thresholds are operational gates, not a claim of
statistical proof.

## Local verification

```bash
python3 scripts/verify_route_artifact.py \
  --artifact tests/fixtures/routes/route_t0_valid.json

python3 scripts/verify_route_artifact.py \
  --artifact tests/fixtures/routes/route_t1_valid.json

# Expected to fail: T2 cannot enter the canonical store.
python3 scripts/verify_route_artifact.py \
  --artifact tests/fixtures/routes/route_t2_rejected.json

# Rejection-audit mode is allowed.
python3 scripts/verify_route_artifact.py \
  --artifact tests/fixtures/routes/route_t2_rejected.json \
  --allow-t2-audit

python3 -m unittest tests/test_route_artifact.py -v
```

## Deliberate non-goals

This slice does not add model integrations, a finding graph, a marketplace,
global model rankings, hidden chain-of-thought storage, or action authority.
