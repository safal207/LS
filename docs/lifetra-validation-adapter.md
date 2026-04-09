# Lifetra Validation Adapter

## Core separation

The validator and Lifetra should remain separate because they solve different problems:

- `CollectiveAnswerValidator` decides which candidate wins.
- Lifetra records how that decision can be inspected later.

That separation matters because winner selection is a scoring and safety decision,
while provenance is an audit and explanation concern. If both were merged into one
component, it would be easy to accidentally create a second validator with slightly
different semantics.

Short version:

`Validator decides. Lifetra records and explains why.`

## Scoring vs provenance

Scoring answers questions such as:

- which candidate passed thresholds,
- which candidate had better relevance and lower hallucination risk,
- whether the accepted set was convergent, weak, conflicted, or rejected.

Provenance answers different questions:

- which candidates were present,
- which candidates supported or contradicted each other,
- which candidate became the winner,
- which global risk flags were active when the decision was made.

The validator owns the first set of concerns. The Lifetra adapter owns the second.

## Why the adapter is thin

After inspecting `safal207/Lifetra`, the current Python bridge in `lifetra_py`
exposes a small Rust-backed trajectory surface:

- `Timestamp`
- `StateTransition`
- `TrajectoryState`

It does **not** currently expose native graph, node, or edge objects in Python.

Because of that, the adapter intentionally uses the real Lifetra surface only for
what Lifetra already provides well:

- create a trajectory container,
- append ordered transitions,
- finalize into a stable textual `summary()`.

Candidate nodes, support links, contradiction links, and acceptance/rejection
status are exported as stable artifact metadata rather than forced into a fake
graph API.

## How support and contradiction are captured

The adapter records topology in artifact metadata:

- candidate nodes include acceptance state, score, preview, reasons, and risk flags,
- support relations are emitted as `supports` edges,
- contradiction relations are emitted as `contradicts` edges,
- accepted and rejected candidates are also linked to the final validation result,
- the selected winner is linked with a dedicated `winner` edge.

At the same time, Lifetra receives a sequence of `StateTransition` events so the
validation run has a compact temporal narrative and a Lifetra-generated summary.

## Why this helps auditability

This split improves auditability because it preserves two layers at once:

- the validator's deterministic decision outcome,
- a separate provenance artifact that explains what the candidate field looked like.

That makes it easier to review why a winner was chosen, which contradictions were
present, and which global risks were active, without letting the trace backend
rewrite the validator's semantics.

It also creates a clean path toward future collective oversight, where downstream
systems can inspect provenance, compare multiple validation runs, or attach higher
level governance checks without touching core scoring logic.

## Current limitations

- no semantic paraphrase clustering yet; the adapter only exports normalized text hashes and previews
- no dynamic feedback from Lifetra into validator score calculation yet
- no distributed consensus integration yet
