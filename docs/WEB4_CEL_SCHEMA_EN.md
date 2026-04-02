# Web4 + Cognitive Economy Layer (CEL) — English Summary

This document is a compact English version of the CEL architecture and formulas.

## Core Layers

1. Runtime — agent execution and proposal generation.
2. CTL — immutable cognitive/economic event ledger.
3. CEM — real-time event mesh.
4. CEL — wallets, listings, buy/subscribe, settlement hooks.
5. LTP — long-term reputation and policy feedback.

## Contribution Economy

Instead of winner-takes-all, CEL rewards the contribution chain:

- hypothesis
- refinement
- validation
- extension

Contribution score:

```text
score = impact * resonance * accuracy
```

Payout split:

```text
payout_i = V * (score_i / Σscore)
```

## Dynamic Pricing

Baseline formula:

```text
price_ct = base_price
         * (1 + alpha * reputation_score)
         * (1 + beta  * demand_index)
         * (1 + gamma * confidence_calibrated)
         * risk_discount
```

`PriceEngine` also returns a resonance band for safe repricing:

- `suggested_resonance_band_min`
- `suggested_resonance_band_max`

## Production Guardrails Implemented

- Minimum stake/deposit for proposal creation: **5 CT**.
- Per-agent rate limit: **max 10 create/hour** and **max 10 buy/hour**.
- Signed CTL events support via `nacl.signing` (`EventSigner`).
- `outcome_settled` includes `agent_id` to avoid expensive LTP joins.

## Current MVP Status

Implemented modules:

- `wallet_api.py`
- `decision_api.py`
- `settlement_worker.py`
- `reputation_engine.py`
- `price_engine.py`
- `contribution_api.py`
- `signing.py`

Tested end-to-end path:

```text
publish -> buy -> settle -> reputation update -> reprice
```
