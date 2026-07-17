# LS — Exact-Head PR Risk Audit

[English](#english) · [Русский](#russian)

<p align="center">
  <a href="LOTUS.md">
    <img src="assets/lotus.svg" alt="LS Lotus Layer" width="170" />
  </a>
</p>

<p align="center">
  <strong>The Lotus Layer</strong><br />
  Clarity from complexity · Evidence before confidence · Memory without authority · Human authorship at the center
</p>

<p align="center">
  <a href="LOTUS.md">Read the living principles / Прочитать принципы Лотоса</a>
</p>

[![LS Exact-Head Audit CLI](https://github.com/safal207/LS/actions/workflows/ls-audit-cli.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/ls-audit-cli.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](LICENSE)

> **LS freezes one pull request at one exact commit and produces an evidence-backed, advisory-only risk Scorecard.** `NOT_RUN`, stale evidence, missing credentials, and incomplete collection never become success.
>
> **LS фиксирует один pull request на одном точном SHA и формирует доказательный advisory-only Scorecard.** Непройденные проверки, устаревшие данные и неполные evidence никогда не превращаются в успех.

## Start here

Use this path when you need to audit a high-impact or AI-generated GitHub pull request.

```bash
git clone https://github.com/safal207/LS.git
cd LS
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install ./packages/ls-audit-cli

ls-audit https://github.com/OWNER/REPO/pull/123 \
  --expected-head 0123456789abcdef0123456789abcdef01234567
```

For a private repository, set `GITHUB_TOKEN` before running the command. LS v0.1 sends that token only to `api.github.com` and never writes it to the audit bundle.

The command produces:

```text
manifest.json
scorecard.json
SCORECARD.md
adjudication-template.json
evidence/
```

Read the generated `SCORECARD.md` first. The evidence directory is the reproducible support for the verdict, not the customer-facing summary. See the [CLI package documentation](packages/ls-audit-cli/README.md) for the full operator boundary.

## Verdict boundary

```text
PR URL + expected 40-character SHA
        ↓
initial exact-head check
        ↓
frozen evidence collection
        ↓
final exact-head check
        ↓
PASS / HOLD / NOT_RUN / INCOMPLETE
        ↓
human adjudication
        ↓
JSON + Markdown Scorecard
```

- An initial or final head mismatch fails closed.
- A force-push during collection cannot produce PASS.
- `CHANGES_REQUESTED` produces HOLD.
- Commentary-only, stale, missing, or unavailable review evidence is incomplete.
- Human adjudication cannot waive exact-head identity.
- LS is advisory-only and cannot approve or merge a pull request.

## Product proof and operator docs

- [The Lotus Layer — living project principles](LOTUS.md)
- [LS v0.1 Product Scorecard](docs/LS_V0_1_PRODUCT_SCORECARD.md)
- [Exact-Head Audit operator runbook](docs/LS_EXACT_HEAD_AUDIT_CLI.md)
- [CLI package documentation](packages/ls-audit-cli/README.md)
- [Issue #904 — installable operator path](https://github.com/safal207/LS/issues/904)

## Package boundary

The supported customer installation is:

```bash
python -m pip install ./packages/ls-audit-cli
```

The repository root `pyproject.toml`, Rust/Maturin build, GhostOS modules, vision/audio stack, and ML dependencies are **legacy research infrastructure**. They are not required for the Exact-Head PR Risk Audit and should not be installed by audit customers.

The previous full architecture, conformance, identity, memory, route-stability, and research README is preserved unchanged at [`README_LEGACY.md`](README_LEGACY.md).

---

<a name="english"></a>

## English

LS reduces the risk of accepting AI-generated changes by binding each conclusion to an exact commit, real execution status, frozen evidence, and human adjudication. It does not claim perfect recall and does not convert unavailable reviewers into approval.

<a name="russian"></a>

## Русский

LS снижает риск принятия AI-generated изменений: каждый вывод привязан к точному commit, реальному статусу выполнения, замороженным evidence и человеческой adjudication. LS не обещает идеальную полноту поиска и не считает недоступного reviewer одобрением.
