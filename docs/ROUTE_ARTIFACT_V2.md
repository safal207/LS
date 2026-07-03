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

- a declared Git host, repository, ref and exact commit;
- a local checkout whose `origin`, `HEAD`, declared ref and commit all match;
- sandbox execution;
- an executable replay command;
- matching expected and observed exit codes;
- passing deterministic assertions;
- an evidence digest.

A 40-character hexadecimal string alone is not T0 evidence.

Only T0 may contribute to confirmed metrics, route promotion, or a
training/distillation corpus.

### T1 — artifact-attested

T1 requires inspectable artifacts and explicit human sign-off, but it does not
claim deterministic replay or verified source-checkout binding. T1 may be stored
as experimental evidence, but it cannot contribute to any confirmed metric,
promotion, or training eligibility.

The first seed route references the live review experiments in:

- `safal207/LS#770`;
- `safal207/robys-coffee-house-demo#153`.

Those runs remain T1 until replayable evidence and outcomes exist.

### T2 — narrative-only

T2 has no reproducible artifact. It is rejected from the canonical store. The
verifier may parse it only in rejection-audit mode so the rejection reason can
be recorded without promoting the narrative into route evidence.

## Canonical content identity

Each route version has a SHA-256 content digest. The digest covers the whole
artifact with `integrity.content_digest` normalized to `null` before hashing.

Canonicalization:

- recursively normalizes all strings and object keys to Unicode NFC;
- sorts object keys;
- uses compact UTF-8 JSON;
- rejects NaN, positive infinity and negative infinity;
- rejects key collisions created by Unicode normalization.

This defines the portable subset used by LS for content addressing.

## Immutable versions and lineage

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

Missing references, self-supersession, duplicate references, and direct or
multi-hop cycles fail closed. Registry cycle detection is iterative so a deep
valid lineage cannot escape through Python recursion depth.

## Route stages

Stages refer to roles and capability classes, not provider brands. Dependencies
must be strings, unique, and reference existing earlier stages. Invalid arrays,
missing dependencies and cycle-shaped ordering fail with stable
`RouteArtifactError` codes rather than raw runtime exceptions.

## Registry statuses

- `draft` — incomplete contract work;
- `experimental` — valid artifact with insufficient promotion evidence;
- `candidate` — T0 evidence and configured quantitative gates pass;
- `validated` — candidate gates plus required maintainer approval pass;
- `deprecated` — historically valid but obsolete;
- `revoked` — unsafe or invalid and must not be recommended.

A non-T0 artifact is explicitly barred from `candidate` and `validated`.

The initial promotion policy requires at least 20 T0 runs, two repositories,
two task variants, one sealed honeypot, no unresolved critical false negatives,
confidence intervals, and maintainer approval. These are operational gates, not
a claim of statistical proof.

## One deterministic verification command

The verification environment must provide `jsonschema` version 4.23 or newer.
Then run:

```bash
python3 scripts/verify_route_contract.py
```

That single command validates the JSON Schema, materializes a real local Git
checkout for T0 source binding, verifies T0 and T1, proves canonical T2
rejection plus rejection-audit acceptance, and runs all mutation/contract tests.

For a single artifact:

```bash
python3 scripts/verify_route_artifact.py \
  --artifact path/to/route.json \
  --repo-root path/to/its/checked-out-repository
```

`--repo-root` is mandatory for T0 ingestion. `--allow-t2-audit` is valid only
with `--artifact`; combining it with registry projection is rejected.

## Deliberate non-goals

This slice does not add model integrations, a finding graph, a marketplace,
global model rankings, hidden chain-of-thought storage, or action authority.
