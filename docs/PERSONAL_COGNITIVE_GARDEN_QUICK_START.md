# Personal Cognitive Garden Quick Start

This is the smallest local path for running the Personal Cognitive Garden demo.

It does not require the full Python/Rust stack, a backend service, Node.js, a
local model, or API keys. It only reads checked-in example files and prints the
reviewer-facing artifact flow.

## 1. Run the human-readable demo

From the repository root:

```bash
python scripts/run_personal_cognitive_garden_demo.py
```

If your shell exposes Python as `python3`, use:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py
```

## 2. Run the JSON output

```bash
python scripts/run_personal_cognitive_garden_demo.py --json
```

This prints the same demo as machine-readable JSON, which is useful for tests,
review artifacts, dashboards, or downstream tooling.

## Expected output fields

The demo output is intentionally small:

| Field | Plain-language meaning |
| --- | --- |
| `session_id` | Which example AI session is being replayed. |
| `session_type` | What kind of session the example represents. |
| `development_class` | The kind of human-development signal LS detected. |
| `is_developmental` | Whether the session should count as development evidence. |
| `human_skill_delta` | The skill or capability change proposed from the session. |
| `capital_effect` | How the accepted update may compound future work. |
| `practice_needed` | What the person should keep practicing. |
| `compounding_score` | A fixture score from the checked-in example, not a benchmark claim. |
| `proposed_status` | The update begins as a proposal, not durable state. |
| `review_decision` | The human review decision in the sample accepted graph. |
| `reviewed_by` | Who accepted the sample update. |
| `accepted_nodes` | The human-owned graph entries that exist after review. |

The key point is the governance shape:

```text
AI session
-> proposed development update
-> human review
-> accepted private graph state
```

## Files the demo reads

```text
examples/personal_cognitive_garden/session_summary.json
examples/personal_cognitive_garden/proposed_update.json
examples/personal_cognitive_garden/accepted_graph_state.json
```

## Go deeper

- Full PCG runner guide: [`PERSONAL_COGNITIVE_GARDEN_RUNNER.md`](PERSONAL_COGNITIVE_GARDEN_RUNNER.md)
- Grant reviewer path: [`../GRANT.md`](../GRANT.md)
- Full runtime setup for advanced contributors: [`../README.md#quick-start`](../README.md#quick-start)
