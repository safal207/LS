# LS Living Evidence Graph v0.1

The Living Evidence Graph extends exact-head review from changed-line inspection to cross-artifact, spatial, temporal, and phase-aware evidence.

```text
exact-head artifacts
-> explicit typed relations
-> deterministic structural probes
-> attributed observations
-> strict phase transitions
-> harmonization
-> dormant regression memory
```

## Dimensions

- **Time:** observed, valid, superseded, and reconciled timestamps are timezone-aware.
- **Space:** every node is bound to repository, base SHA, head SHA, branch, workflow, and runtime context when available.
- **Phase:** transitions are strictly linear: `LATENT -> UNFOLDED -> REPRODUCED -> CONFIRMED -> BLOCKING -> FIXED -> VERIFIED -> DORMANT`.
- **Unfolding:** a counterexample recipe identifies how a latent contradiction could become observable; it is not automatically an executed reproduction.
- **Attenuation:** the active defect disappears after repair, but its regression rule remains dormant and executable.
- **Observation:** effect, observer, method, evidence, and repeatability are recorded separately.
- **Harmonization:** schema, runtime, fixtures, tests, docs, and workflows converge through evidence rather than model averaging.

## Evidence tiers

| Tier | Meaning |
| --- | --- |
| `T0_REPRODUCTION` | Deterministic counterexample executed against the exact reviewed artifact |
| `T1_STRUCTURAL` | Static contradiction or risky structural pattern between related artifacts |
| `T2_INDEPENDENT_MODELS` | Independently confirmed model analysis |
| `T3_MODEL_HYPOTHESIS` | Single-model candidate |

A counterexample recipe attached to a T1 finding is guidance for reproduction, not proof that the candidate artifact was executed.

## Artifact relations

Edges are created only from explicit relation evidence. Artifact-kind compatibility alone is insufficient and must never create a cross-product.

```text
VALIDATOR     --IMPLEMENTS--> JSON_SCHEMA
FIXTURE       --VALIDATES-->  JSON_SCHEMA
TEST          --TESTS-->      VALIDATOR
SPECIFICATION --DOCUMENTS-->  VALIDATOR
WORKFLOW      --INVOKES-->    VALIDATOR / TEST
```

Each relation hint must name its exact source path, target path, relation type, and supporting evidence. Automatic relationship discovery is a later acquisition-layer responsibility and must emit the same explicit hints.

## Synthetic pattern specimen inspired by PR #796

The checked-in specimen contains deliberately minimal snippets with five known structural signatures inspired by findings discussed on PR #796:

1. closed-object schema/runtime parity drift;
2. digest-pattern parity drift;
3. naive/aware timestamp comparison risk;
4. CLI/spec command divergence;
5. missing `UiDismissed` coverage signature.

The specimen verifies only that the probe implementation recognizes those signatures and avoids selected false positives. It is **not** a byte-for-byte or semantic replay of PR #796, does not exercise the real reducer, and does not establish recall against the real exact-head artifacts.

A real benchmark requires exact-head artifact acquisition, frozen result hashes, independent review, and adjudication against real files.

## Boundary

This layer produces review evidence. It cannot approve or merge a pull request. A repaired finding becomes `DORMANT` only after exact-head verification, and the regression rule remains active for future reviews.
