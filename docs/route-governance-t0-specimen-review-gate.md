# Route governance T0 specimen review gate

## Status

Review checklist for the manual specimen introduced by PR `#772`.

This document does not define a normative schema or a generic governance runtime. It defines the evidence required before the Draft PR may be considered ready for independent review.

## Objective

Evaluate whether the route domain can reuse the existing governance envelope and lifecycle invariants without pretending that route and identity candidates are the same type.

The specimen under review is:

`examples/route-governance/route-governance-t0-manual-specimen.json`

The expected architecture outcome is Variant B:

```text
shared governance envelope
+ domain-specific candidate
+ domain-specific durable record
+ shared ledger principles
+ domain-specific projection
```

## Gate result classes

### PASS

All mandatory checks pass and no semantic field loss, self-approval path, authority escalation, or projection inconsistency is found.

### PASS WITH BOUNDARY

The specimen proves the shared governance envelope and lifecycle principles, but domain-specific schemas must remain separate. This is the expected result.

### FAIL

Any mandatory check fails, the candidate digest cannot be reproduced, route evidence is lost, a candidate can attest its own approval, immutable history is mutated, or the active state cannot be reconstructed from ledger entries.

## Mandatory checks

| ID | Check | Required evidence | Failure condition |
|---|---|---|---|
| RG-01 | Candidate digest binding | Independent canonical SHA-256 recomputation equals `GovernanceDecision.subject_digest` and `RouteVersionRecord.candidate_digest` | Any digest mismatch or ambiguous canonicalization |
| RG-02 | Proposer/approver separation | `promotion_candidate.proposed_by` differs from `governance_decision.decided_by` | Same actor, missing actor, or indirect self-approval path |
| RG-03 | Evidence preservation | T0 tier, exact HEAD, replay digest, honeypot result, metrics, and counterevidence remain reachable from the candidate/record chain | Silent field loss or evidence copied into an unverifiable summary only |
| RG-04 | Promotion floor honesty | One-run fixture projects only `experimental`; it cannot claim `candidate`, `validated`, or maintainer approval | Stronger state projected from insufficient evidence |
| RG-05 | Immutable supersession | A later route version would create a new candidate, decision, record, and ledger events while preserving old record bytes | In-place mutation, history deletion, or rewritten prior approval |
| RG-06 | Deterministic projection | Removing the snapshot and replaying ordered ledger entries reconstructs the same active version and state | Snapshot contains authority or state that cannot be derived from ledger |
| RG-07 | Counterevidence survival | Empty counterevidence is explicit; future counterevidence must bind to a new decision/revalidation path | Counterevidence can be dropped, hidden, or appended without lifecycle effect |
| RG-08 | No action authority | Candidate, decision, record, and snapshot grant no merge, deploy, execution, tool, or memory-write authority | Any route-memory state directly authorizes a protected side effect |
| RG-09 | Domain semantic integrity | Route fields remain route-specific; no identity-only continuity/profile semantics are required | Route is forced into `IdentityProposalCandidate` or nullable cross-domain super-schema |
| RG-10 | Reproducible exact-head evidence | T0 fixture remains bound to source repository, declared ref, commit, local checkout, and exact HEAD through the existing verifier | A syntactically valid SHA alone is accepted as T0 evidence |

## Independent digest result

The candidate object in the current specimen was independently canonicalized using:

- Unicode NFC normalization;
- recursively sorted object keys;
- compact UTF-8 JSON;
- finite JSON values only.

Expected digest:

```text
sha256:104faf6094421ea4ed65e8756abe2ef87db2f778383033a3ebcf543ee8ef0fba
```

The same value must appear in:

- `candidate_digest.value`;
- `governance_decision.subject_digest`;
- `route_version_record.candidate_digest`.

Any candidate edit invalidates the decision and requires a fresh digest and review.

## Draft-to-ready prerequisites

PR `#772` may move from Draft to Ready for review only when all of the following are true on the same exact head:

1. Route Artifact v2 workflow is green.
2. Security & CI Pipeline is green.
3. Regression Scan, Ruff, and repository E2E checks are green.
4. RG-01 through RG-10 have no known failure.
5. No open P0/P1 correctness, security, governance, or evidence-integrity finding remains.
6. The PR description or a durable PR comment states that the generic runtime is not proven.
7. The scope freeze remains in force.
8. At least one independent reviewer is explicitly asked to evaluate the specimen boundary rather than only the JSON syntax.

Moving to Ready does not approve merge. It only opens the exact head for independent review.

## Reviewer questions

The reviewer should answer:

1. Does the specimen preserve all route-specific evidence without importing identity semantics?
2. Can the decision be independently tied to the exact candidate reviewed?
3. Is `experimental` the strongest state justified by the fixture?
4. Can supersession occur without mutating the old version record?
5. Can the active route state be rebuilt using only ordered immutable history?
6. Is there any hidden path from route memory to action authority?
7. Does the specimen support Variant B, or is compatibility weaker/stronger than expected?

## Exit decision

After review, record exactly one result:

- `VARIANT_A_PROVEN` — shared normative candidate/record/projection types are justified;
- `VARIANT_B_PROVEN` — shared decision envelope and lifecycle principles only;
- `VARIANT_C_REQUIRED` — separate schemas plus conformance tests only;
- `MORE_EVIDENCE_REQUIRED` — specimen is insufficient or internally inconsistent.

The default is not Variant A. Stronger reuse requires stronger proof.
