# LS Contributor Pack

Status: **one-command contributor entrypoint for network precision runs**.

The Contributor Pack is the easiest way to test LS on a local machine, IDE, or
model runtime and send a useful result back to the project.

It turns the current deterministic probes into a small folder:

```text
reports/contributor_pack/
  README.md
  issue_body.md
  network_precision_contributor_report.md
  network_precision_contributor_report.json
  pack_summary.json
```

## Quick Start

From the repository root:

```bash
python scripts/prepare_contributor_pack.py --runner your-github-handle
```

Then open:

```text
reports/contributor_pack/issue_body.md
```

Paste it into:

- [Contributor call: test Network Precision Gain on your models](https://github.com/safal207/LS/issues/571)

## What The Pack Runs

The pack includes the same public probes used by the contributor protocol:

- network precision gain;
- model roster readiness;
- Nash-style route stability proxy;
- network trajectory and observer velocity;
- conductor noise robustness;
- safe sample live-model pilot.

Live model calls are opt-in:

```bash
python scripts/prepare_contributor_pack.py \
  --runner your-github-handle \
  --live \
  --max-tokens 180
```

Use `--live` only when your local or hosted model routes are intentionally
configured.

## IDE Entry

VS Code / Cursor:

```text
Terminal -> Run Task... -> LS: Prepare Contributor Pack
```

OpenCode:

```text
/ls-contributor-pack your-github-handle
```

## Machine Output

For automation:

```bash
python scripts/prepare_contributor_pack.py \
  --runner your-github-handle \
  --json
```

To also create a zip archive:

```bash
python scripts/prepare_contributor_pack.py \
  --runner your-github-handle \
  --zip
```

## Boundary

This pack is not a model leaderboard, not a formal Nash proof, and not a
production-safety claim. It is a reproducible way to answer a narrower question:

```text
On this environment, did the cooperative route and evidence stack improve
visible task precision over the single-answer baseline?
```

Do not include secrets, API keys, private prompts, customer data, or proprietary
code in a public contributor run.
