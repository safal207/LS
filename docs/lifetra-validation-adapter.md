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

## Consensus hardening now implemented

On top of the base validator and Lifetra trace layer, LS now includes a
deterministic governance overlay that adds:

- semantic paraphrase clustering without embeddings, using token and shingle similarity
- history-aware advisory score correction based on past rounds
- agent reputation memory across rounds
- quorum-style distributed consensus snapshots
- repeated coalition and corruption-risk alerts across history

This layer is advisory by design. It does not silently rewrite the base
validator's `winner_agent_id`. Instead it produces a governance report with:

- adjusted candidate scores,
- a governed winner candidate,
- paraphrase clusters,
- reputation profiles,
- coalition alerts,
- and distributed consensus status.

## Consensus Failure Modes and How LS Resists Them

A multi-model consensus system fails not only when it selects the wrong answer,
but when it cannot explain how that answer emerged. In practice, model-consensus
networks tend to break in recurring ways: false agreement, hidden conflict,
opaque winner selection, and weak consensus disguised as confidence.

Our design addresses these problems by keeping the validator and the trace layer
separate:

- the validator decides
- Lifetra records and explains why

This gives the system both a decision layer and a provenance layer.

### 1. Opaque winner selection

**Failure mode:**
The network returns a winner, but there is no durable record of why that model
won, which alternatives were rejected, or what risks were active at selection
time.

**How LS resists it:**
`CollectiveAnswerValidator` produces the winner deterministically, and the
Lifetra-backed trace adapter records:

- the winner,
- the accepted and rejected candidates,
- the consensus status,
- the global risk flags,
- a stable summary artifact for later review.

This turns answer selection from an opaque event into an inspectable decision.

### 2. Echo-chamber consensus

**Failure mode:**
Several agents repeat the same weak answer, creating the appearance of
consensus without independent support or genuine quality.

**How LS resists it:**
The validator already flags `possible_echo_chamber` when multiple low-quality
candidates collapse onto the same normalized text. The trace layer preserves
that moment as an artifact, so false agreement becomes auditable rather than
silently accepted.

This helps distinguish:

- real convergence,
- from synthetic agreement produced by repetition.

### 3. Hidden contradiction between strong candidates

**Failure mode:**
Two or more high-scoring candidates disagree in substance, but the network
collapses the disagreement into a single returned answer without exposing the
conflict.

**How LS resists it:**
Contradictions are preserved both in validation logic and in trace metadata.
The adapter emits contradiction relations as explicit edges and carries forward
`conflict_between_top_candidates` into the trace artifact.

This means the system no longer hides disagreement inside the final answer.

### 4. Single-model dominance disguised as consensus

**Failure mode:**
Only one candidate is truly acceptable, but the network presents the result as
if a broad consensus exists.

**How LS resists it:**
When only one candidate is accepted, the validator marks
`single_point_consensus`. The trace artifact preserves that condition, so
reviewers can distinguish:

- broad agreement,
- from isolated acceptance.

This is critical for identifying fragile decisions.

### 5. Loss of rejected-candidate context

**Failure mode:**
Once a winner is selected, the system forgets why other candidates lost. Over
time this destroys auditability and makes governance impossible.

**How LS resists it:**
The trace artifact preserves accepted and rejected candidates, along with their
scores, previews, reasons, and risk flags. The network therefore retains
field-level context, not just the final winner.

### 6. False equivalence between support and correctness

**Failure mode:**
A candidate appears strong because other candidates support it, even if the
support structure is shallow, circular, or derivative.

**How LS resists it:**
Support is recorded explicitly as support edges rather than being treated as
unquestioned proof. This allows later inspection of whether support was:

- broad,
- narrow,
- circular,
- or suspiciously concentrated.

The system does not confuse visible support with proven truth.

### 7. No durable provenance after the round ends

**Failure mode:**
The system can reason in the moment, but once the round is over, there is no
durable record of how consensus formed.

**How LS resists it:**
The Lifetra adapter uses the real Lifetra Python surface to build a temporal
trace through:

- `TrajectoryState`
- `StateTransition`
- `Timestamp`

This provides a compact temporal narrative of the validation process, while
candidate topology remains available in stable metadata.

### 8. Accidental creation of a second validator

**Failure mode:**
A provenance or observability layer gradually starts influencing winner
selection, resulting in hidden duplicated decision logic and semantic drift.

**How LS resists it:**
The architecture is explicitly split:

- validator decides,
- Lifetra records.

The trace backend is optional and post-decision only. It does not modify
scoring, acceptance thresholds, or winner selection in this phase.

That prevents the trace system from becoming an unaccountable second authority.

### 9. Weak foundation for governance and oversight

**Failure mode:**
The system may work operationally, but it cannot support later review, policy
enforcement, anomaly detection, or coordination-level oversight.

**How LS resists it:**
By producing stable validation trace artifacts, LS creates a foundation for:

- post-hoc audit,
- dashboard inspection,
- reviewer workflows,
- future routing policy analysis,
- future governance and collective oversight layers.

This means the current system remains simple, while future control layers can
be built on top of preserved evidence.

## What this layer gives the network

This layer gives the model-consensus network:

- a record of who won,
- a record of who was rejected,
- visibility into support and contradiction structure,
- preserved global risk context,
- a temporal trace of the decision process,
- and a durable artifact for future audit and oversight.

In short, the network no longer knows only what it decided.
It also knows how that decision was formed.

## Current limits of consensus hardening

This is now a much stronger foundation, but it is still not the final
governance system. Current limits include:

- paraphrase clustering is heuristic and deterministic, not embedding-based semantic reasoning
- score correction is advisory and exposed in governance reports; it does not replace the base validator decision path
- reputation memory is lightweight and history-based, not a full trust-economy or cryptographic identity system
- distributed consensus is currently a quorum-style governance snapshot, not a full BFT-like protocol
- coalition detection is history-aware and useful for anomaly surfacing, but not yet a full automated enforcement system

## Core principle

The central design principle remains:

`Validator decides. Lifetra records and explains why.`
