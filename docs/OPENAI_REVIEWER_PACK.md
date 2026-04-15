# OpenAI Reviewer Pack

This pack is optimized for a fast technical review of four public AI safety repos.

Review order:

1. `L-THREAD` for deterministic replay, hallucination blocking, and audit-ready traces
2. `Causal-Memory-Layer` for causal accountability and permission lineage
3. `DMP` for non-rewritable decision memory
4. `LRI` for identity continuity and anti-capture protocol design

## 1. L-THREAD

Repo:
- `https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-`

Open first:
- `README.md`
- `docs/devtools/quickstart.md`
- `specs/LTP-Spec-v0.1.md`
- `tools/ltp-inspect/inspect.ts`

Run:

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm test:conformance
```

What the reviewer should see:
- deterministic replay surface for trace inspection
- explicit hallucination-blocking / contract-enforcement posture
- stable inspector snapshots and conformance checks
- model-agnostic audit surface rather than vendor-specific prompting tricks

Strongest signal:
- the repo now has a reviewer-safe green validation path on `main`

## 2. Causal Memory Layer

Repo:
- `https://github.com/safal207/Causal-Memory-Layer`

Open first:
- `README.md`
- `docs/`
- `safety_eval/`
- `benchmarks/`

Run:

```bash
python -m pytest -q
```

What the reviewer should see:
- causal audit engine for checking whether actions are grounded in valid lineage
- safety-eval framing that is closer to empirical accountability than abstract philosophy
- a concrete Python validation surface that runs cleanly

Strongest signal:
- causal accountability is implemented as a testable audit layer, not just described

## 3. Decision Memory Protocol

Repo:
- `https://github.com/safal207/DMP-decision-memory-protocol`

Open first:
- `README.md`
- `schema/`
- `docs/`
- `validator/`

Run:

```bash
python -m unittest discover -s tests -q
```

What the reviewer should see:
- a protocol for non-rewritable decision memory
- explicit structure around append-only records and boundary violations
- a small but legible validation surface

Strongest signal:
- decision irreversibility is treated as a protocol primitive, not a logging afterthought

## 4. Living Relational Identity

Repo:
- `https://github.com/safal207/Living-Relational-Identity-LRI`

Open first:
- `README.md`
- `docs/SECURITY_MODEL.md`
- `docs/architecture/lri-trust-model.md`
- `protocol/lri/schema/identity.yaml`

Run:

```bash
python -m pytest -q
python scripts/validate_project.py
```

What the reviewer should see:
- identity continuity and anti-capture framed as protocol / governance problems
- a Python reference implementation rather than only conceptual writing
- root-level reviewer flow now works cleanly

Strongest signal:
- identity protection is translated into testable invariants and drift/authority logic

## Fast Path For Reviewers

If time is limited, review in this order:

1. `L-THREAD README + pnpm test`
2. `Causal-Memory-Layer README + pytest`
3. `LRI README + SECURITY_MODEL + pytest`
4. `DMP README + tests`

That sequence gives the fastest picture of:
- deterministic auditability
- causal accountability
- decision memory
- identity continuity safeguards

## Core Thesis Across The Four Repos

These projects are trying to make AI system behavior:
- legible
- replayable
- causally attributable
- non-deniable after the fact

The common thread is not "more agent capability".
The common thread is accountability infrastructure for agentic systems.

## Current Review Notes

As of `2026-04-10`:
- `L-THREAD main` has a green reviewer-safe validation path
- `LRI main` has a green root-level pytest flow
- `Causal-Memory-Layer` already ran clean locally
- `DMP` already ran clean locally

## One-Sentence Positioning

`L-THREAD` blocks and replays hallucination-prone agent traces.  
`CML` checks whether an action was causally authorized.  
`DMP` makes decisions non-rewritable.  
`LRI` protects human identity continuity from optimization and capture.
