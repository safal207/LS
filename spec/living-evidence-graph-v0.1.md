# LS Living Evidence Graph v0.1

The Living Evidence Graph extends exact-head review from changed-line inspection to cross-artifact, spatial, temporal, phase-aware, and reproducible evidence.

```text
exact-head artifacts
-> explicit typed relations
-> deterministic structural probes
-> safe counterexample reproduction
-> attributed observations
-> strict phase transitions
-> evidence-backed harmonization
-> dormant regression memory
```

## Dimensions

- **Time:** observed, valid, superseded, reconciled, decision, and transition timestamps are timezone-aware and monotonic.
- **Space:** every node is bound to repository, base SHA, head SHA, branch, workflow, runtime, and canonical artifact path when available.
- **Phase:** transitions are strictly linear: `LATENT -> UNFOLDED -> REPRODUCED -> CONFIRMED -> HARMONIZED -> BLOCKING -> FIXED -> VERIFIED -> DORMANT`.
- **Unfolding:** a structural probe and counterexample recipe identify how a latent contradiction becomes observable.
- **Reproduction:** a T0 result records the concrete trusted input, observed result, linked finding IDs, and whether the contradiction reproduced.
- **Attenuation:** the active defect disappears after repair, but its regression rule remains dormant and executable.
- **Observation:** event, observer, method, evidence, repeatability, and observation time remain distinct.
- **Harmonization:** a `HarmonizationDecision` records the chosen contract, evidence, observation attribution, and decision time. Entering `HARMONIZED` without that decision is rejected.

## Evidence tiers

| Tier | Meaning |
| --- | --- |
| `T0_REPRODUCTION` | A deterministic counterexample was executed by the trusted reproduction harness against the supplied declarative contract or extracted rule. |
| `T1_STRUCTURAL` | Static contradiction or risky structural pattern between related artifacts. |
| `T2_INDEPENDENT_MODELS` | Independently confirmed model analysis. |
| `T3_MODEL_HYPOTHESIS` | Single-model candidate. |

A counterexample recipe attached to a T1 finding is guidance for reproduction. It becomes T0 only after the trusted harness executes the declared input and records the observed result.

## Artifact references and relations

Repository paths are the public input API. `node_id_for_path()` validates and converts a canonical relative POSIX path to the internal node ID. `LivingEvidenceGraph.add_signal()` accepts either a repository path or an existing node ID and normalizes the stored signal reference.

Edges are created only from explicit relation evidence. Artifact-kind compatibility alone is insufficient and must never create a cross-product.

```text
VALIDATOR     --IMPLEMENTS--> JSON_SCHEMA
FIXTURE       --VALIDATES-->  JSON_SCHEMA
TEST          --TESTS-->      VALIDATOR
SPECIFICATION --DOCUMENTS-->  VALIDATOR
WORKFLOW      --INVOKES-->    VALIDATOR / TEST
```

Each relation hint must name its exact source path, target path, relation type, and supporting evidence. Automatic relationship discovery is a later acquisition-layer responsibility and must emit the same explicit hints.

## Deterministic probe set

The v0.1 structural layer emits independent findings for:

1. unknown envelope property;
2. unknown event property;
3. unknown actor property;
4. unknown bindings property;
5. digest-pattern parity drift;
6. naive/aware timestamp comparison risk;
7. CLI/spec command divergence;
8. missing `UiDismissed` coverage.

Shape guards must be executable rejecting key-set checks in the relevant function. Comments, docstrings, unrelated-function guards, and mere mentions of `additionalProperties` do not suppress a finding.

Digest parity is scoped to the value that receives the weak `sha256:` prefix check. An unrelated regex call does not count. Recognized strong checks include exact schema-pattern `re.fullmatch`, anchored `re.match`, and equivalent compiled-regex calls on the same value or a traced helper argument.

Timezone safety requires an enforceable rejection or normalization for the parsed timestamp. Merely reading or logging `.tzinfo` is not a guard.

## Synthetic reproduction specimen inspired by PR #796

The checked-in specimen contains minimal declarative contracts and source signatures derived from the five known finding classes discussed on PR #796. It drives eight T1 signatures and five T0 reproduction records:

1. one reproduction covering unknown envelope, event, actor, and bindings properties;
2. malformed digest accepted by prefix logic but rejected by the schema regex;
3. naive/aware datetime comparison producing `TypeError` in the trusted harness;
4. required CLI flags or referenced paths missing from the documented command;
5. declared `UiDismissed` transition absent from supplied coverage evidence.

The reproduction harness never imports or executes candidate source text. It executes trusted generic mutations and comparisons against declarative schema data and AST-extracted contract behavior.

This is stronger than a static signature specimen but is still **not** the frozen exact-head byte bundle for PR #796. It does not prove recall against the real 17 files or execute the real reducer. That benchmark requires exact-head artifact acquisition, frozen hashes, independent system and Claude runs, and adjudication.

## Boundary

This layer produces review evidence. It cannot approve, comment on, or merge a pull request. A repaired finding becomes `DORMANT` only after exact-head verification, and its regression rule remains active for future reviews.
