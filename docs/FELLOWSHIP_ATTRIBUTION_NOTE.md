# Fellowship Attribution Note

This note explains what the LS council ledger currently measures, how contribution is computed, what receiver resonance means in the current implementation, and what the merit sync layer adds.

The goal is to let a reviewer understand the method without reading the full codebase.

## Scope

The current attribution method is built around one artifact per council cycle:

- [`artifacts/council-ledger/<cycle_id>.json`](../artifacts/council-ledger)

The canonical schema is defined in:

- [`python/ls/cognition/council_contribution_ledger.py`](../python/ls/cognition/council_contribution_ledger.py)

The current roadmap and integration plan are described in:

- [`docs/COUNCIL_CONTRIBUTION_LEDGER_ROADMAP.md`](COUNCIL_CONTRIBUTION_LEDGER_ROADMAP.md)

## What the council ledger records

Each ledger records one coordination cycle with five main layers:

1. goal
2. network context
3. participants
4. final decision
5. outcome and attribution

In plain language, the ledger answers:

- who participated
- what each participant proposed
- which route or proposal was selected
- whether the cycle succeeded
- whether the result resonated with the receiver
- who contributed the most to the final result

## What a participant means

Each participant currently includes:

- `model_id`
- `model_type`
- `proposal_id`
- `proposal_summary`
- `route_hint`
- `confidence`
- `latency_ms`
- `token_cost`
- `selected`
- `weight_in_final_decision`

This is not a full causal explanation of the model internals. It is a cycle-level structured summary of the model's role in the council.

## How contribution is computed

Contribution is not treated as "who was right in isolation."

Instead, the current method tries to measure contribution to collective success.

For each participant, the ledger computes:

- `adoption_score`
- `outcome_lift`
- `stability_impact`
- `receiver_resonance`
- `cost_efficiency`

These are combined into `total_contribution_score`.

### 1. Adoption score

Adoption score captures whether the participant's proposal influenced the final decision.

It currently combines:

- whether the participant was selected
- whether the participant's route matched the final selected route
- the participant's explicit weight in the final decision

This is the closest current field to "did this model actually matter to the final answer?"

### 2. Outcome lift

Outcome lift measures whether the final cycle was good in practice.

It is derived from:

- success
- path quality
- network improvement

This means a participant benefits when the final cycle was not only accepted, but also improved the route and the wider network state.

### 3. Stability impact

Stability impact measures whether the cycle remained controlled and low-friction.

It uses:

- drift detected or not
- whether operator intervention was required
- operator feedback score
- receiver resonance score

This matters because a correct answer with high friction is less useful in a safety-oriented coordination system.

### 4. Receiver resonance

Receiver resonance is tracked explicitly as its own factor.

The current ledger treats resonance as:

- did the answer land cleanly with the receiver
- did it reduce friction rather than increase it
- did it move the cycle toward acceptance instead of revision

This is not yet a human-annotated social metric. It is currently runtime-derived from cycle signals.

### 5. Cost efficiency

Cost efficiency is meant to discourage expensive or slow contributions that do not justify their cost.

It currently combines:

- normalized latency
- normalized token cost
- normalized confidence

This keeps the attribution method from rewarding only high-weight proposals regardless of operational cost.

## Current contribution formula

The current implementation combines the sub-scores approximately as:

- `0.30 * adoption_score`
- `0.25 * outcome_lift`
- `0.20 * stability_impact`
- `0.15 * receiver_resonance`
- `0.15 * cost_efficiency`

This yields `total_contribution_score`.

The highest-scoring participant becomes:

- `best_contributor_model_id`
- `best_contributor_score`

The current method is best understood as a practical attribution heuristic, not a proof of causal credit assignment.

## What receiver resonance means

Receiver resonance is currently represented by:

- `receiver_type`
- `receiver_resonance_score`
- `receiver_acceptance_label`

In the current LS implementation, resonance is an outcome-facing signal that tries to capture whether the answer was received in a way that reduced friction and made coordination easier.

Right now, this score is derived from runtime signals such as:

- softening or de-escalation signals
- goal alignment
- cooperative participation
- intervention requirement

This is useful, but still limited.

It should not be described as a validated human-preference metric yet.

## What merit sync adds

After the council ledger is produced, the system maps it into CEL contribution, reputation, and merit signals.

Relevant code:

- [`python/modules/cel/council_sync.py`](../python/modules/cel/council_sync.py)
- [`python/modules/cel/merit_sync.py`](../python/modules/cel/merit_sync.py)

This adds three practical layers:

1. contribution records
2. reputation updates
3. merit and network-effect updates

### Contribution records

Each participant is converted into a `ContributionRecord` that carries:

- proposal id
- agent id
- contribution type
- impact
- resonance
- accuracy proxy

This gives the repository a replayable contribution layer outside the raw council JSON.

### Reputation updates

The current CEL sync computes a `quality_score` from the council outcome using:

- path quality
- operator feedback
- receiver resonance
- success

That score is then combined with contribution score to update per-model reputation.

This means reputation is no longer only a generic event counter. It becomes grounded in real cycle outcomes.

### Merit updates

The merit layer adds a network-facing interpretation of the same cycle.

It combines:

- quality score
- speed score
- reliability score
- contribution score
- alignment score
- a small `network_effect_bonus`

This is the first step toward rewarding synergy-positive participation rather than only isolated output quality.

## What the current method does well

The current method already does three important things well:

1. it records one structured artifact per council cycle
2. it links participant contribution to outcome quality rather than only proposal presence
3. it connects attribution to downstream reputation and merit signals

For a fellowship reviewer, this is already enough to show a real safety-oriented measurement direction rather than only aspirational framing.

## Known limitations

The current attribution method still has important weaknesses.

### 1. It is heuristic, not causal

The method attributes credit based on structured cycle signals and weighted heuristics.

It does not prove that a given participant causally produced the outcome.

### 2. Many real cycles still have weak participant identity

In the current evidence corpus, many cycles still show:

- `model_id = "callable:unknown"`
- `route = "unknown"`

This weakens the precision of model-level attribution.

### 3. Receiver resonance is runtime-derived

The current resonance signal is useful, but it is not independently human-labeled.

That makes it promising instrumentation, not yet a validated benchmark target.

### 4. Small evidence corpus

The curated fellowship dataset currently contains:

- `8` selected ledgers

This is enough for a compact evidence package, but not enough for strong statistical claims.

### 5. No packaged replay traces yet

The current dataset package reserves `traces/`, but it does not yet include replay traces.

That makes the attribution package easier to inspect than to reproduce end-to-end.

## Open questions

The next research-facing questions are:

1. how much attribution should depend on route adoption versus downstream outcome
2. how receiver resonance should be human-labeled or externally evaluated
3. how to distinguish useful dissent from noise in multi-model councils
4. how to improve participant identity so local versus web contribution is measurable more cleanly
5. how to package replay traces alongside ledgers for better reproducibility

## Bottom line

The current attribution layer should be described as:

- a structured council-cycle attribution method
- tied to real runtime artifacts
- connected to reputation and merit
- promising for safety and oversight evaluation
- still limited by small data, heuristic credit assignment, and weak participant identity in some local cycles

That is an honest and defensible description of the current system.
