# LS v0.1 Product Scorecard

**Product claim:** LS reduces the risk of accepting AI-generated pull requests by binding every review result to reproducible evidence: an exact commit, an identified reviewer/model, explicit execution status, adjudicated findings, and a human-readable verdict.

**Release status:** **RELEASE CANDIDATE.** The Robys external pilot and the Grok 4.5 provenance control are verified. LS v0.1 requires one more external exact-head pilot before release tagging.

## Repeatable review contract

A result counts only when all of these are present:

1. the PR scope and exact 40-character head SHA;
2. deterministic checks with their real status;
3. each AI reviewer identified by provider/model or bot identity;
4. `NOT_RUN`, missing credentials, stale evidence, or model mismatch recorded as incomplete — never converted into success;
5. findings confirmed, rejected, or left unresolved by human adjudication;
6. fixes and the final verdict bound to the same evidence trail.

## Proof A — Robys causal delivery closure

| Scorecard field | Result |
| --- | --- |
| What LS checked | Whether a reviewed AI-generated change actually reached the customer path, whether its evidence stayed valid after later commits, and whether two discovered delivery tails were genuinely closed. |
| Evidence | Append-only causal fixtures for the historical wordmark risk, the open delivery tails, and the later closure; deterministic causal-trail and delivery-tail validators; exact-head CI. |
| Agents | Qodo, CodeRabbit, Grok, deterministic LS validators, and maintainer adjudication. |
| What they found | A generated-content compatibility risk; a reviewed wordmark that had not reached `main`; and a CTA destination exposing one pairing while Discover contained two active journeys. Independent review of the LS validator also found crash paths, hidden-blocker omission, an illegal `MERGED` state with an unsatisfied guard, and missing mutation coverage. |
| Confirmed findings | Both product delivery tails were confirmed. The validator findings were accepted as real correctness gaps. |
| Fixes delivered | [Robys #173](https://github.com/safal207/robys-coffee-house-demo/pull/173) delivered the production-referenced wordmark; [Robys #167](https://github.com/safal207/robys-coffee-house-demo/pull/167) delivered two pairing offers and source parity. The validator findings were fixed and covered by regression tests in [LS #792](https://github.com/safal207/LS/pull/792). |
| Exact heads | Wordmark: `ed9b736bea78d3eabdc70bde21b29df338348a73`; pairing closure: `e3f2a14696e9bc3ff5ab2f87829e5540019a39b9`; LS closure proof: `f927c2766839ede8d02729d6995e5972497fa3b4`. |
| Verdict | **PASS — CAUSAL CLOSURE VERIFIED.** Risk was found, corrective changes were delivered, and the history was closed by a new snapshot without rewriting the earlier open-state evidence. |

Canonical evidence:

- [Historical wordmark fixture](https://github.com/safal207/LS/blob/f927c2766839ede8d02729d6995e5972497fa3b4/ls-conformance/causal_phase_trail/fixtures/robys_pr_164_wordmark.json)
- [Open delivery-tail fixture](https://github.com/safal207/LS/blob/f927c2766839ede8d02729d6995e5972497fa3b4/ls-conformance/causal_phase_trail/fixtures/robys_pr_165_open_delivery_tails.json)
- [Append-only closure fixture](https://github.com/safal207/LS/blob/f927c2766839ede8d02729d6995e5972497fa3b4/ls-conformance/causal_phase_trail/fixtures/robys_pr_167_closed_delivery_tails.json)
- [Causal conformance run](https://github.com/safal207/LS/actions/runs/29102784233) and [delivery-tail run](https://github.com/safal207/LS/actions/runs/29102784162), both successful on the LS proof head

## Proof B — Grok 4.5 provenance gate

| Scorecard field | Result |
| --- | --- |
| What LS checked | Whether the advisory reviewer used the exact requested model and whether a model-generated review was published only after the provider identity matched. |
| Evidence | Production xAI Chat Completions run, preserved review artifact, requested/provider identifiers in the artifact header, and a guarded publication path for missing or mismatched provenance. |
| Agents | Grok 4.5, CodeRabbit, the deterministic provenance gate, and maintainer adjudication. |
| What they found | Floating aliases made the actual model ambiguous. Exact equality could also suppress reviews if the provider returned another ID, so the live provider response had to be verified rather than assumed. |
| Confirmed findings | The old alias was not adequate provenance. On the final run, the requested model and provider-returned model were both exactly `grok-4.5`. |
| Fixes delivered | [LS #858](https://github.com/safal207/LS/pull/858) pinned the request, preserved both IDs, rejected missing/mismatched provider identity, emitted stable diagnostics, and suppressed the model verdict on provenance failure. |
| Exact head | `1fcf29a4a3db8e99206a11e55bf998fb56bf8e0e`. |
| Verdict | **PASS — MODEL PROVENANCE VERIFIED.** The workflow requested `grok-4.5`, xAI returned `grok-4.5`, and only then did LS publish the Grok review. |

Canonical evidence:

- [Grok PR Review run #182](https://github.com/safal207/LS/actions/runs/29103778774)
- [Preserved review artifact](https://github.com/safal207/LS/actions/runs/29103778774/artifacts/8231953915), digest `sha256:11a5acb9c972fb49d07b4fcf52579fe2155c4b00f06cfa615cb40e9733a8515b`
- Artifact header: `Requested model: grok-4.5. Provider model: grok-4.5.`

A green advisory job alone is not a model success. If the reviewer is `NOT_RUN`, credentials are missing, or provenance is absent/mismatched, LS records an incomplete lane or diagnostic and publishes no model verdict.

## v0.1 release gate

| Gate | Status |
| --- | --- |
| Robys external causal proof | **PASS** |
| Grok 4.5 provenance proof | **PASS** |
| Second external exact-head pilot | **PENDING** |
| Two-case comparison | **PENDING** |
| LS v0.1 tag | **BLOCKED until the two pending gates pass** |

The product-level success criterion is not “the AI found many bugs.” It is: evidence is reproducible; SHA and reviewer identity are exact; incomplete execution is visible; findings can be confirmed or rejected; and a person can understand the decision without knowing LS internals.
