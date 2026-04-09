# Fellowship Evidence Sprint

This sprint is designed to strengthen the repository for a fellowship
application in 1 to 2 days of focused work.

## Sprint goal

Turn the current repository from:

- strong prototype with good framing

into:

- strong prototype with a compact evidence package

## Deliverables

1. a small real council-cycle corpus
2. a replayable dataset folder
3. a benchmark note
4. a contribution-attribution note

## Task 1. Generate real council-cycle artifacts

Target:

- at least 10 real council cycles

Output:

- `artifacts/council-ledger/*.json`

Guidelines:

- prefer real council-cycle runs over demo generation
- avoid low-signal dry-run artifacts in the final evidence set
- keep a small manifest of which artifacts are considered evidence-grade

Done when:

- there are at least 10 non-demo, non-empty cycles

## Task 2. Package a small replayable dataset

Target:

- one compact folder with selected evidence artifacts

Suggested structure:

```text
artifacts/fellowship-dataset/
  manifest.json
  ledgers/
  traces/
  README.md
```

Include:

- selected ledger artifacts
- trace exports where available
- one short README explaining fields

Done when:

- a reviewer can open one folder and understand the sample set

## Task 3. Write a benchmark note

Target file:

- `docs/FELLOWSHIP_BENCHMARK_NOTE.md`

Include:

- benchmark goal
- baseline
- measured scenarios
- metrics
- limitations

Use as starting evidence:

- `ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json`

Done when:

- the benchmark can be cited without sounding like a marketing claim

## Task 4. Write an attribution note

Target file:

- `docs/FELLOWSHIP_ATTRIBUTION_NOTE.md`

Include:

- what the council ledger measures
- how contribution is computed
- what receiver resonance means
- what merit sync adds
- known limitations and open questions

Done when:

- a reviewer can understand the method without reading the full codebase

## Task 5. Refresh the public scorecard from better evidence

Target:

- rebuild the scorecard from higher-quality council cycles

Output:

- refreshed `councilScorecard.json`

Done when:

- the public scorecard reflects more than two weak cycles

## Suggested execution order

1. generate real cycles
2. curate dataset folder
3. write benchmark note
4. write attribution note
5. refresh public scorecard

## Best possible outcome for this sprint

At the end of the sprint, the repository should have:

- a credible demo
- a small benchmark
- a small dataset
- a short technical note

That is enough to materially strengthen the application narrative.
