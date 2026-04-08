# Fellowship Research Outputs

This document defines the strongest concrete outputs to produce from this
repository for a safety fellowship or research-oriented review.

## Output 1. Council quality benchmark

Goal:

- measure whether council cycles improve route quality, receiver resonance,
  and operator burden relative to simpler baselines

Possible metrics:

- route win rate
- receiver resonance score
- operator intervention rate
- council value score
- cost-to-quality ratio

## Output 2. Replayable council trace dataset

Goal:

- publish a small dataset of replayable council cycles and associated metadata

Contents:

- council ledger artifact
- trace export
- selected route
- contribution breakdown
- receiver outcome

Why it matters:

- supports reproducible analysis
- gives a concrete evaluation corpus

## Output 3. Contribution attribution note

Goal:

- write a short technical note on how LS attributes value inside multi-model councils

Topics:

- proposal adoption
- outcome lift
- resonance with the receiver
- merit updates
- limits of attribution

## Output 4. Approval-safe workflow demo

Goal:

- show a complete human-in-the-loop path where model output is not trusted blindly

Demo path:

- task creation
- inspection
- approval or rejection
- trace export
- replay / post-hoc review

Why it matters:

- demonstrates operator oversight instead of autonomous black-box execution

## Output 5. Quality intelligence note

Goal:

- explain how CI quality gates, quality snapshots, and LiminalQA integration
  support evaluation and triage over time

Focus:

- machine-readable reports
- failure classification
- threshold enforcement
- run history

## Best near-term package

If time is limited, the highest-value package is:

1. one short demo
2. one small benchmark
3. one replayable trace dataset
4. one short note on contribution attribution

That package is much stronger than broad product claims without artifacts.
