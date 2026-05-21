# Fellowship Reviewer Script

This is the shortest reliable script for showing LS to a fellowship reviewer,
mentor, or screening panel in roughly 60 to 90 seconds.

## 30-second version

Use this when the reviewer only gives you one minute.

> LS is not an assistant wrapper or a generic assistant wrapper. It is a local-first coordination and oversight runtime for human-plus-model systems.
>
> The key thing it does is turn multi-model reasoning into measurable artifacts: council ledgers, contribution scores, receiver resonance, merit signals, approval-safe workflows, and replayable traces.
>
> In one command I can run a council cycle, emit a ledger artifact, refresh the curated evidence dataset, and update the public scorecard. So the system is evaluated and inspectable, not just generative.

## 60 to 90-second version

Use this when you have enough time to narrate the demo while running it.

> I want to show LS as an oversight and coordination runtime, not as another assistant shell.
>
> The core idea is that multi-model decisions should leave behind evidence. In LS, a council cycle produces a machine-readable ledger that records who participated, what route was selected, how the outcome was received, and which model contributed most to the final result.
>
> That ledger is not just a log. It feeds contribution, reputation, and merit layers, and it can be replayed or inspected later. We also connect this to CI quality gates and LiminalQA-style quality snapshots, so evaluation is part of the runtime rather than a separate afterthought.
>
> For the demo, I run one command. It emits a council ledger, refreshes the evidence dataset, and updates the public scorecard. Then I open one ledger and one scorecard snapshot. What I want you to take away is that LS makes model coordination measurable, reviewable, and safer to supervise.

## Demo command

```powershell
python tools/run_fellowship_demo.py "Run a council coordination cycle for this operator request" --llm-mode auto
```

Fallback:

```powershell
python tools/run_fellowship_demo.py "Run a council coordination cycle for this operator request" --llm-mode dry-run
```

## What to point at on screen

1. The printed `cycle_id`, `selected_route`, and `best_contributor_model_id`.
2. The emitted council ledger in `artifacts/council-ledger/`.
3. The refreshed `artifacts/fellowship-demo/demo-summary.json`.
4. The refreshed public scorecard snapshot in `ghostgpt-ls-landing/src/data/councilScorecard.json`.

## One-sentence closing

> The point of LS is not just to produce answers, but to make coordinated model behavior observable, attributable, and governable.
