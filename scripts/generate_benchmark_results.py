#!/usr/bin/env python3
"""Generate benchmark/RESULTS.md from the existing benchmark and dataset artifacts.

Sources:
  ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json
  artifacts/fellowship-dataset/manifest.json

Output:
  benchmark/RESULTS.md

Run from the repository root:
  python3 scripts/generate_benchmark_results.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OPERATOR_BENCHMARK = ROOT / "ghostgpt-ls-landing" / "src" / "data" / "operatorDeltaBenchmark.json"
FELLOWSHIP_MANIFEST = ROOT / "artifacts" / "fellowship-dataset" / "manifest.json"
OUTPUT = ROOT / "benchmark" / "RESULTS.md"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required source not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def format_scenario_table(scenarios: list[dict]) -> str:
    rows = []
    rows.append("| Scenario | Seconds | Commands | Tasks reviewed |")
    rows.append("|---|---|---|---|")
    for s in scenarios:
        rows.append(
            f"| `{s['name']}` | {s['seconds']} | {s['commands']} | {s['tasks_reviewed']} |"
        )
    return "\n".join(rows)


def format_summary_table(summary: dict) -> str:
    rows = []
    rows.append("| Metric | Value |")
    rows.append("|---|---|")
    rows.append(f"| Tasks reviewed | {summary['tasks_reviewed']} |")
    rows.append(f"| Seconds saved vs manual LTP | {summary['seconds_saved_vs_manual_ltp']} |")
    rows.append(f"| Batch speedup vs manual LTP | {summary['batch_speedup_vs_manual_ltp_pct']}% |")
    rows.append(f"| Manual review commands | {summary['manual_review_commands']} |")
    rows.append(f"| Batch review commands | {summary['batch_review_commands']} |")
    rows.append(f"| Command reduction | {summary['command_reduction_pct']}% |")
    return "\n".join(rows)


def format_dataset_table(manifest: dict) -> str:
    s = manifest["summary"]
    rows = []
    rows.append("| Metric | Value |")
    rows.append("|---|---|")
    rows.append(f"| Ledger count | {s['ledger_count']} |")
    rows.append(f"| Success count | {s['success_count']} |")
    rows.append(f"| Failure count | {s['failure_count']} |")
    rows.append(f"| Avg receiver resonance | {s['avg_resonance']} |")
    rows.append(f"| Avg best-contributor score | {s['avg_contribution']} |")
    return "\n".join(rows)


def build_results(op: dict, manifest: dict) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scenario_table = format_scenario_table(op["scenarios"])
    summary_table = format_summary_table(op["summary"])
    dataset_table = format_dataset_table(manifest)

    limitations = "\n".join(f"- {l}" for l in manifest["limitations"])

    return f"""\
# Benchmark Results

> Generated: {generated_at}
> Source: `scripts/generate_benchmark_results.py`
> Raw data: `ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json`, `artifacts/fellowship-dataset/manifest.json`

---

## 1. Operator workflow benchmark

Benchmark environment: {op['environment']['platform']}, Python {op['environment']['python']}, queue size {op['environment']['queue_size']}.

### Scenarios

{scenario_table}

### Summary

{summary_table}

**Strongest result:** command count reduced from `{op['summary']['manual_review_commands']}` to `{op['summary']['batch_review_commands']}` ({op['summary']['command_reduction_pct']}% reduction) for a queue of {op['summary']['tasks_reviewed']} approval-sensitive tasks.

**Disclaimer:** {op['investor_takeaway']['disclaimer']}

---

## 2. Council-ledger dataset sample

Source: `artifacts/fellowship-dataset/manifest.json`

{dataset_table}

**Excluded from selection:** {', '.join(manifest['selection_policy']['excluded'])}.

---

## 3. Limitations

{limitations}

---

## 4. What these results support

- LS reduces operator coordination overhead for replayable approval-queue review.
- Structured council-cycle artifacts can be curated into a small evidence dataset.
- The scaffolding for stronger oversight, contribution-attribution, and approval-safe review is operational.

## 5. What these results do not support

- General model superiority.
- Universal latency improvements.
- Statistically strong performance claims across environments.
- Human-annotated resonance or adoption quality.
- Route-quality leadership (many current cycles still expose `route = "unknown"`).

See `docs/FELLOWSHIP_BENCHMARK_NOTE.md` for full methodology and next-upgrade recommendations.
"""


def main() -> None:
    op = load_json(OPERATOR_BENCHMARK)
    manifest = load_json(FELLOWSHIP_MANIFEST)
    content = build_results(op, manifest)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Written: {OUTPUT}")


if __name__ == "__main__":
    main()
