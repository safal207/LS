# Tradernet Lotus human-impact scorecard

**Verdict:** `HUMAN_REVIEW_REQUIRED`  
**Case:** `tradernet-public-web-2026-07-18`  
**Canonical scorecard SHA-256:** `baeea2938098bcf06ced7eabeaf3e402643ea85d2af29348edbc00a4a05eda61`

This scorecard consumes the Pythia judgment and the canonically validated CML public Memory Pack. It does not perform a new scan and does not contact Tradernet.

## Human-impact order

| Rank | Finding | Severity | Why it matters |
|---:|---|---|---|
| 1 | Mobile public chart returns 404 | P1 | A phone user completely loses access to a public analytical capability and receives no useful supported-state explanation. |
| 2 | Mobile hero is discovered late | P1-performance | The user waits several avoidable seconds before the page appears meaningful and may interpret the delay as failure. |
| 3 | Hidden mobile terminal image downloads | P2 | The user pays data, battery, and time cost for a 346,800-byte resource that renders at `0×0`. |
| 4 | Missing terminal onboarding asset | P3 | No visible break was confirmed, but the product creates redundant request and diagnostic noise. |

## Seven-petal result

1. **Clarity from complexity — pass with gap.** The evidence is separated cleanly, but the product's generic mobile 404 does not explain what happened.
2. **Evidence before confidence — pass.** Confirmed claims are bound to exact runs and artifact digests.
3. **Causes before symptoms — partial.** Specific causes are isolated, while the single shared mobile root cause remains unproven.
4. **Memory without authority — pass.** CML remembers the cluster without approving a report or converting a hypothesis into fact.
5. **Consent before durable memory — pass.** Only public unauthenticated evidence is retained.
6. **Repair before judgment — pass.** Each finding has a concrete repair path and no blame or security claim.
7. **Human authorship at the center — pass.** A human decides whether to report, publish, prioritize, or act.

## Decision

The first two findings are ready for separate primary reports. The terminal findings are suitable as secondary reports or attachments. Market-open quote freshness and reconnect testing remain a separate experiment.

Machine-readable scorecard: `docs/lotus-cases/tradernet-human-impact-v1.json`.
