# Fellowship Application Ready Pack

This document is the single entry point for using this repository in a fellowship application.

It is designed for fast reuse:

- what to say in one sentence
- what to say in one paragraph
- what to show in a short demo
- what evidence to link
- what claims are safe to make

## 30-second version

LS is a local-first coordination and oversight runtime for human-plus-model systems.

It turns multi-model reasoning into reviewable council cycles with measurable contribution, receiver resonance, replayable traces, human approval, and quality-gated evaluation artifacts.

## 90-second version

This repository is not centered on chatbot UX. It focuses on the safety and oversight layer around agentic systems.

LS records council cycles as structured artifacts, measures which model actually contributed to the final result, tracks how well the answer resonated with the receiver, routes those outcomes into contribution, reputation, and merit signals, and keeps the process inspectable through replayable traces and operator approval flows.

The project also includes quality gates, machine-readable quality reports, and LiminalQA integration so runs can be inspected over time instead of only judged by a single pass/fail signal.

## What the repository already demonstrates

The current repository already shows five concrete capabilities:

1. human-in-the-loop approval-safe workflows
2. council-cycle artifacts with measurable attribution
3. receiver-resonance instrumentation
4. replay and inspection for tasks and coordination traces
5. evaluable quality infrastructure with CI gates and machine-readable reports

## Best links to give a reviewer

Start with:

- [`docs/OPENAI_SAFETY_FELLOWSHIP_POSITIONING.md`](OPENAI_SAFETY_FELLOWSHIP_POSITIONING.md)
- [`docs/FELLOWSHIP_APPLICATION_BRIEF.md`](FELLOWSHIP_APPLICATION_BRIEF.md)
- [`docs/FELLOWSHIP_ONE_PAGER.md`](FELLOWSHIP_ONE_PAGER.md)

Then move to evidence:

- [`docs/FELLOWSHIP_BENCHMARK_NOTE.md`](FELLOWSHIP_BENCHMARK_NOTE.md)
- [`docs/FELLOWSHIP_ATTRIBUTION_NOTE.md`](FELLOWSHIP_ATTRIBUTION_NOTE.md)
- [`artifacts/fellowship-dataset/manifest.json`](../artifacts/fellowship-dataset/manifest.json)

Then move to implementation:

- [`python/ls/cognition/council_contribution_ledger.py`](../python/ls/cognition/council_contribution_ledger.py)
- [`python/modules/cel/council_sync.py`](../python/modules/cel/council_sync.py)
- [`python/modules/cel/merit_sync.py`](../python/modules/cel/merit_sync.py)
- [`python/ls/agent_shell/cli.py`](../python/ls/agent_shell/cli.py)

## Safest claims to make

These claims are currently well supported:

- LS is an oversight-oriented coordination runtime.
- LS records structured council-cycle artifacts.
- LS measures participant contribution heuristically at the cycle level.
- LS tracks receiver resonance as an explicit runtime signal.
- LS supports replayable inspection and approval-safe operator workflows.
- LS includes machine-readable quality reporting and gating infrastructure.

## Claims to avoid or soften

These claims should be softened or avoided:

- "We solved model alignment."
- "This proves causal attribution."
- "This benchmark shows universal performance gains."
- "Receiver resonance is a validated human-preference metric."
- "The current scorecard is production-grade evaluation."

Use instead:

- "early evidence"
- "structured instrumentation"
- "initial benchmark"
- "heuristic attribution layer"
- "compact evidence package"

## Suggested application attachments

If the application allows links or supplementary materials, the minimum useful package is:

1. repository link
2. [`docs/FELLOWSHIP_ONE_PAGER.md`](FELLOWSHIP_ONE_PAGER.md)
3. [`docs/FELLOWSHIP_DEMO_PATH.md`](FELLOWSHIP_DEMO_PATH.md)
4. [`docs/FELLOWSHIP_BENCHMARK_NOTE.md`](FELLOWSHIP_BENCHMARK_NOTE.md)
5. [`artifacts/fellowship-dataset/README.md`](../artifacts/fellowship-dataset/README.md)

## Suggested live demo order

For a short review call or recorded walkthrough:

1. show the operator-facing framing
2. run a council cycle
3. show the emitted ledger artifact
4. show contribution and resonance fields
5. show the public scorecard
6. close with the benchmark note and dataset package

Detailed path:

- [`docs/FELLOWSHIP_DEMO_PATH.md`](FELLOWSHIP_DEMO_PATH.md)

## Evidence snapshot as of now

The current package includes:

- a curated fellowship dataset with `8` council-ledger artifacts
- a benchmark note based on operator-review measurements
- an attribution note explaining the current method
- a refreshed public scorecard sourced from the curated dataset

This is enough to present the repository as a credible early research-and-engineering artifact rather than only an aspirational concept.

## Best framing sentence for interviews or forms

LS is a local-first coordination and oversight runtime that makes multi-model reasoning reviewable, replayable, and measurable through council-cycle artifacts, contribution tracking, receiver resonance, and approval-safe operator workflows.

## Next milestone after application

If asked what comes next, the strongest answer is:

- improve participant identity beyond `callable:unknown`
- add replay traces to the curated dataset
- expand the council corpus
- add stronger external or human-labeled resonance evaluation
- turn the current compact package into a stronger benchmark and dataset release
