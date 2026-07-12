# LS v0.1 Product Scorecard

**Product claim:** LS reduces the risk of accepting AI-generated pull requests by binding every review result to reproducible evidence: an exact commit, an identified reviewer/model, explicit execution status, adjudicated findings, and a human-readable verdict.

**Release status:** **RELEASED.** Two external pilots and the Grok 4.5 provenance gate are verified. The annotated tag `ls-v0.1` is published and resolves exactly to release commit `14e2abdcf6d97df48fc6a2fe4887cccea3cb0501`. LS v0.1 releases the repeatable evidence-and-adjudication contract; it does not certify every reviewed target as safe.

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

## Proof C — ibex reviewer-gate pilot

| Scorecard field | Result |
| --- | --- |
| What LS checked | A real three-file, security-sensitive AI reviewer bootstrap in another repository: secret isolation, exact-head binding, untrusted diff parsing, reviewer execution status, and whether green CI justified acceptance. |
| Evidence | Frozen target files and Git blobs; exact-head CI/job status; independent CodeRabbit findings; a blind Grok 4.5 artifact; explicit adjudication; and a later fix-head compare. |
| Agents | CodeRabbit, Qodo, Grok 4.5, deterministic CI, Ibex Verilator E2E, DeepSeek contract validation, and human adjudication. The DeepSeek model lane is explicitly `NOT_RUN`. |
| What they found | CodeRabbit found three major defects: cross-event cancellation, a force-push head race, and patch-body path allowlist contamination. Qodo independently reproduced the head race, missed two known defects, added one private-repo portability risk, and produced one rejected permission false positive. Grok partially reproduced the parser defect, confirmed the green-vs-`NOT_RUN` evidence problem, missed two known defects, and produced one rejected false positive. |
| Confirmed findings | All three CodeRabbit findings were confirmed against the frozen source. Qodo's head-race finding was confirmed; its private-repo opt-in finding is scoped to future portability; its permission finding was rejected because GitHub accepts `Pull requests: write` for PR issue comments. Grok F1 was rejected because YAML dedentation preserves the marker at column 0; one defense-in-depth candidate remains unresolved. |
| Fixes delivered | Follow-up head `e0b465f131dad4ff6300c66e9fb8660757d94cff` adds event-scoped concurrency, checks the current head before and after diff fetch, restricts paths to `diff --git` metadata, and adds regression coverage. Exact-head CI and Ibex E2E passed. |
| Exact heads | Vulnerable target: `afc29b1db985d705c90c91685ad4460cf981a805`; LS carrier: `90573c90c01060d8d9373e170e17a4af31d8f7e1`; fix recheck: `e0b465f131dad4ff6300c66e9fb8660757d94cff`. |
| Verdict | **PRODUCT-PROOF PASS.** The separate target verdict is **REQUEST_CHANGES / HOLD** despite green workflows. The later fixes are confirmed; the DeepSeek model lane remains incomplete and contributes no positive evidence. |

Canonical evidence:

- [External target PR #57](https://github.com/safal207/ibex-agent-verification/pull/57) and [frozen compare](https://github.com/safal207/ibex-agent-verification/compare/4db48bc4eab67390e38542cbe676bb3cba2dd9b6...afc29b1db985d705c90c91685ad4460cf981a805)
- [LS pilot PR #861](https://github.com/safal207/LS/pull/861) with frozen files, [Qodo review](https://github.com/safal207/LS/pull/861#issuecomment-4937152602), and adjudication records
- [Grok PR Review run #198](https://github.com/safal207/LS/actions/runs/29105494882) and [artifact 8232627268](https://github.com/safal207/LS/actions/runs/29105494882/artifacts/8232627268), digest `sha256:2e00df8de5ed4a14a49780bde2bcfcf7fdc4a4e6e4244c1ce8e74e73190978ac`
- Grok artifact header: `Requested model: grok-4.5. Provider model: grok-4.5.`
- Vulnerable-head runs: [CI #708](https://github.com/safal207/ibex-agent-verification/actions/runs/28337168705), [DeepSeek #18](https://github.com/safal207/ibex-agent-verification/actions/runs/28337168706), [Ibex E2E #188](https://github.com/safal207/ibex-agent-verification/actions/runs/28337168708)
- Fix-head runs: [CI #720](https://github.com/safal207/ibex-agent-verification/actions/runs/28338283813), [DeepSeek #21](https://github.com/safal207/ibex-agent-verification/actions/runs/28338283812), [Ibex E2E #192](https://github.com/safal207/ibex-agent-verification/actions/runs/28338283801)

The DeepSeek model job was skipped because this bootstrap workflow did not yet exist on the trusted base for its own `pull_request_target` review. LS v0.1 accepts this lane only as explicit incomplete evidence: the required external pilot review was supplied independently by verified Grok 4.5 plus CodeRabbit/Qodo, and DeepSeek contributes no PASS signal.

## Release acceptance boundary

- **What v0.1 certifies:** LS can repeatably freeze an external PR, preserve reviewer/model identity, distinguish execution from `NOT_RUN`, adjudicate findings, verify fixes, and issue a bounded verdict.
- **What v0.1 does not certify:** the vulnerable ibex head, every AI reviewer, complete recall, or an unresolved/unevaluated lane.
- **Why target HOLD is not a release blocker:** a correct HOLD is the expected product output for a risky target; turning it into PASS would invalidate the proof.
- **Accepted incomplete lane:** DeepSeek remains `NOT_RUN` and is explicitly excluded from positive evidence. This is a documented scope decision, not a waiver that upgrades the lane.

## Release evidence audit — 2026-07-12

- [x] Vulnerable target, carrier, and fix SHAs resolve and match the frozen files.
- [x] Vulnerable-head and fix-head workflow jobs were inspected individually; skipped model jobs remain `NOT_RUN`.
- [x] Grok run #198 artifact digest and `requested=provider=grok-4.5` header were verified.
- [x] CodeRabbit, Qodo, and Grok findings were reconciled with confirmed, rejected, scoped, and unresolved outcomes in LS #861.
- [x] README relative link and bilingual release-proof entry were checked.
- [x] Annotated tag `ls-v0.1` is published and verified identical to release commit `14e2abdcf6d97df48fc6a2fe4887cccea3cb0501` in PR #865.

## Two-case comparison

| Dimension | Robys | ibex PR #57 |
| --- | --- | --- |
| Product surface | Customer-facing wordmark and pairing journey | Secret-bearing AI reviewer workflow |
| Frozen evidence | Historical open snapshots plus append-only closure | Immutable three-file target plus later fix-head compare |
| Deterministic signal | Causal validators and delivery-tail CI passed | CI and E2E passed on both vulnerable and fixed heads |
| Reviewer signal | Qodo, CodeRabbit, and Grok found fail-closed gaps that were fixed | CodeRabbit reproduced 3/3 known defects; Qodo reproduced 1/3 and had 1 rejected false positive; Grok reproduced 1/3, missed 2/3, and had 1 rejected false positive |
| Incomplete lane handling | Stale evidence invalidated instead of reused | Green DeepSeek workflow contained a skipped model job, recorded as `NOT_RUN` |
| Adjudicated outcome | **PASS — delivered closure** | **REQUEST_CHANGES** on vulnerable head; fixes confirmed, model lane still incomplete |
| Product lesson | LS preserves a true past risk and a later successful outcome without rewriting history | LS prevents green CI from laundering an unexecuted model lane or known review defects into acceptance |

The cases differ in repository, domain, evidence shape, and final verdict. Both use the same contract: exact identity, real execution status, independent findings, explicit adjudication, fix evidence, and a verdict that does not exceed the evidence.

## v0.1 release gate

| Gate | Status |
| --- | --- |
| Robys external causal proof | **PASS** |
| Grok 4.5 provenance proof | **PASS** |
| ibex product-proof objective | **PASS — repeatability demonstrated** |
| ibex vulnerable target verdict | **HOLD — three confirmed major defects** |
| ibex fix-head recheck | **FIXES CONFIRMED** |
| DeepSeek model lane | **ACCEPTED INCOMPLETE — `NOT_RUN`, zero positive weight** |
| Human adjudication record | **COMPLETE in LS #861** |
| Two-case comparison | **PASS** |
| README product entry | **PUBLISHED** |
| LS v0.1 annotated tag | **PUBLISHED — `ls-v0.1` → `14e2abdcf6d97df48fc6a2fe4887cccea3cb0501`** |

The product-level success criterion is not “the AI found many bugs.” It is: evidence is reproducible; SHA and reviewer identity are exact; incomplete execution is visible; findings can be confirmed or rejected; and a person can understand the decision without knowing LS internals.
