# LS v0.1 pilot 2 — blind review pack

This directory preserves the exact three-file change from [safal207/ibex-agent-verification#57](https://github.com/safal207/ibex-agent-verification/pull/57) for an LS v0.1 external pilot.

## Frozen target

- Repository: `safal207/ibex-agent-verification`
- Pull request: `57`
- Base: `4db48bc4eab67390e38542cbe676bb3cba2dd9b6`
- Exact head: `afc29b1db985d705c90c91685ad4460cf981a805`
- Changed files: `3`
- Compare: https://github.com/safal207/ibex-agent-verification/compare/4db48bc4eab67390e38542cbe676bb3cba2dd9b6...afc29b1db985d705c90c91685ad4460cf981a805

The files under `target/` are byte-for-byte snapshots from that immutable head:

| Target path | Git blob |
| --- | --- |
| `.github/workflows/deepseek-pr-review.yml` | `1cabf0ce2ccc8d7e71aa7967a2849f6903cba5fc` |
| `scripts/deepseek_pr_review.py` | `a10354027a7086ce290bc77c6622fc5df825a3a0` |
| `tests/test_deepseek_pr_review.py` | `4753aea1687810d02e798fc2107742bf762f4e39` |

## Pre-review execution evidence

These statuses describe execution only; they are not treated as a safety verdict.

| Lane | Run | Status |
| --- | --- | --- |
| Deterministic CI | [CI #708](https://github.com/safal207/ibex-agent-verification/actions/runs/28337168705) | `PASS` |
| Existing model lane | [DeepSeek PR Review #18](https://github.com/safal207/ibex-agent-verification/actions/runs/28337168706) | `PASS` |
| Hardware/E2E lane | [Ibex Verilator E2E #188](https://github.com/safal207/ibex-agent-verification/actions/runs/28337168708) | `PASS` |

## Blind-review rule

The Grok 4.5 review must use only this frozen pack and the PR intent. Prior reviewer findings are sealed until Grok output is preserved. Afterward, a human will classify every finding as confirmed, rejected, or unresolved against the immutable target and independent review evidence.

`NOT_RUN`, missing model provenance, or stale/mismatched SHA must remain incomplete and cannot produce a successful pilot verdict.
