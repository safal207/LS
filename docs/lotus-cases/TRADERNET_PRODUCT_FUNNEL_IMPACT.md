# Tradernet product-funnel human-impact scorecard

**Verdict:** `HUMAN_REVIEW_REQUIRED`  
**Case:** `tradernet-product-funnel-2026-07-21`  
**Scorecard SHA-256:** `326d784d6dffaa72e5af54fc271023fa3cdcf8f35d4d7868a748424d19f30dd3`

## Evidence chain

- LiminalQA product audit: PR `#102`, exact head `d14d0e0cf434000c10609dc8627c288df5306df6`
- Pythia judgment: PR `#238`, exact head `323705b4f7a8ecca3c5a475e2504f2c41e231188`
- CML Memory Pack: PR `#215`, exact head `f0269ee1f9c9237876dcf70fc390a66790a76e55`
- CML pack ID: `d9b886e7b4985dd9c4932232a69a5bfb5caaf70f597051a87dd93357560c4654`
- Lotus Product Lens: PR `#920`, exact head `44087899bdaad86b32b13d89812cbf7a174db2fe`

## Human-impact order

| Rank | Finding | Evidence | Human impact | Recommended action |
|---:|---|---|---|---|
| 1 | Mobile public chart returns generic 404 | `CONFIRMED · P1` | A mobile user loses access to a public analytical capability and receives no useful supported-state explanation. | Repair as a separate mobile public-value item and preserve instrument context. |
| 2 | Mobile hero discovered late | `CONFIRMED · P1-performance` | Meaningful content appears several avoidable seconds late, increasing abandonment and uncertainty about whether the page works. | Fix responsive LCP scheduling and verify with repeated alternating runs. |
| 3 | Hidden mobile terminal image | `CONFIRMED · P2` | The user pays network, battery and time cost for `346,800` bytes that are never visible. | Stop the hidden branch from initiating the request and confirm transfer reduction. |
| 4 | Missing onboarding asset request | `CONFIRMED · P3` | No visible break is proven, but the request creates avoidable network and diagnostic noise. | Remove or correct the obsolete reference. |

## What is ready now

The team can use the package immediately for:

1. four evidence-backed public repair tickets;
2. a P0 authorised validation matrix for desktop and mobile web;
3. P0–P2 product backlog with measurable acceptance criteria;
4. a bounded funnel experiment plan;
5. event, metric and guardrail design;
6. handoff to Product, Design, QA and Analytics.

## What is not ready

The current evidence does **not** justify external defect claims that:

- the authenticated order form hides fees or consequences;
- KYC or funding recovery is broken;
- Stop Loss or Take Profit is unusable;
- mobile web compresses desktop tables;
- users confuse real and demo;
- a proposed funnel will increase conversion;
- one root cause explains all mobile findings;
- a security vulnerability exists.

These remain `HYPOTHESIS`, `NEEDS_AUTHENTICATED_EVIDENCE` or `UNKNOWN`.

## Product priority

### P0 — validate safety, state and control

- persistent real/demo, session and data state;
- complete order consequences preview;
- marketable-limit explanation;
- explicit cancellation state;
- in-context Stop Loss and Take Profit;
- mobile task cards;
- safe mobile draft recovery.

The goal is not more trading activity. The goal is fewer preventable misunderstandings, corrections and support incidents.

### P1 — improve activation without pressure

- intent-segmented public entry;
- demo-first activation;
- preserved activation checklist;
- portfolio attention queue;
- bounded mobile navigation.

Primary metric: `qualified seven-day activation`, not click-through or raw order count alone.

### P2 — deepen value after core reliability

- intent-specific workspaces;
- contextual education;
- portfolio-change explanation;
- bounded recovery reminders.

## Seven product petals

1. **Intent before conversion — partial.** Segmentation is a valid experiment, but the current mismatch has not been measured.
2. **Continuity before friction — needs evidence.** Onboarding, draft and interruption continuity need authorised validation.
3. **Complementary value before upsell — guardrail.** Paid or risk-increasing choices must be relevant, optional and never preselected.
4. **One click without hidden commitment — needs authenticated evidence.** Amount, fee, currency, session and next state must be visible and tested.
5. **Recovery before pressure — guardrail.** Recovery restores intention; it does not pressure a person to trade.
6. **Evidence before growth claims — pass with measurement plan.** Activation is paired with correction, support, complaint and harm signals.
7. **Human freedom at every stage — needs evidence.** Decline, correction, cancellation and challenge paths must be verified.

## ClickFunnels boundary

ClickFunnels is used only to structure a clear journey:

```text
intent → promise → first value → activation → commitment → result → recovery or exit
```

It is not permission to introduce:

- false urgency;
- artificial scarcity;
- pressure to trade;
- preselected paid data, margin or risk-increasing choices;
- hidden recurring terms;
- conversion claims without refunds, churn, complaints and harm signals.

## Recommended human decision

Assign owners for the four confirmed public fixes. Then authorise one safe exact-build authenticated validation pass covering state, order preview, cancellation, protection and mobile recovery before creating any additional defect report.

## Authority boundary

The scorecard is advisory. It does not access accounts, place or cancel orders, contact Tradernet, approve an experiment, deploy, deliver or merge.

Machine-readable scorecard: `docs/lotus-cases/tradernet-product-funnel-impact-v1.json`.
