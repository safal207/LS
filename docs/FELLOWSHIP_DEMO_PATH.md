# Fellowship Demo Path

This demo path is designed for a reviewer, interviewer, or fellowship screener
who needs to understand the repository quickly.

## Goal

Show that LS is not a generic assistant, but a coordination and oversight
runtime with measurable artifacts.

## Demo sequence

### 1. Start from the framing

Show:

- `README.md`
- `docs/OPENAI_SAFETY_FELLOWSHIP_POSITIONING.md`

Say:

- LS is a human-in-the-loop coordination runtime
- it tracks councils, contribution, resonance, and approval-safe workflows

### 2. Run the one-command demo path

Use:

```powershell
python tools/run_fellowship_demo.py "Run a council coordination cycle for this operator request" --llm-mode auto
```

Show:

- `cycle_id`
- selected route
- best contributor
- emitted artifact path
- refreshed `artifacts/fellowship-demo/demo-summary.json`
- refreshed public `councilScorecard.json`

### 3. Open the council ledger artifact

Show:

- `artifacts/council-ledger/<cycle_id>.json`

Point out:

- participants
- decision
- outcome
- contribution breakdown
- receiver resonance

### 4. Show contribution and merit effects

Explain that the cycle is not just logged:

- contribution records are derived
- reputation updates can be applied
- merit and network-effect signals are computed

### 5. Show replay / inspection

Use the CLI or local workflow that exports traces to LTP and explain:

- the trace can be replayed
- the path can be inspected after the fact
- this supports debugging and governance

### 6. Show quality and observability

Show one of:

- local dashboard
- `quality-report.json`
- CI quality gate summary

Point out:

- machine-readable reports
- enforced quality thresholds
- structured triage and history

### 7. Show public scorecard

Open:

- GitHub Pages landing

Point out:

- council scorecard
- contribution frequency
- route wins
- resonance trend
- merit trend

## Fast fallback

If the local LLM is unavailable, the same flow can still be shown in dry-run mode:

```powershell
python tools/run_fellowship_demo.py "Run a council coordination cycle for this operator request" --llm-mode dry-run
```

This is weaker evidence than a live local cycle, but it preserves the same artifact path for a reviewer.

## What the reviewer should walk away with

After this demo, the reviewer should understand:

- the system supports measurable multi-model coordination
- outcomes are inspectable and replayable
- human approval is explicit
- quality is evaluated, not assumed

## Keep the demo short

The best live version is 5 to 7 minutes:

1. framing
2. run one cycle
3. open one ledger
4. show one dashboard or scorecard
5. explain the research direction
