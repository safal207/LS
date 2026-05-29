# README Conductor Entry Patch Prompt

Use this prompt with Codex, Claude Code, or another repo-editing agent.

Goal: make the first LS Conductor CLI visible from the top of `README.md` without expanding or rewriting the README.

## Patch-only instruction

Modify only:

```text
README.md
```

Do not modify code, tests, schemas, workflows, examples, or docs.

## Required English README changes

Near the top English navigation area, after the existing line:

```markdown
New here? Start with: [Why Star LS](docs/WHY_STAR_LS.md) · [2-minute route-stability demo](#2-minute-route-stability-demo) · [Contributor matrix](https://github.com/safal207/LS/issues/563)
```

add:

```markdown
Developer quickstart: [LS Conductor Quickstart](docs/CONDUCTOR_QUICKSTART.md) · first CLI: `python scripts/ls_conductor_review_pr.py --base HEAD~1 --head HEAD --json`
```

In the English `## First 10 seconds` section, after the paragraph that defines the core loop:

```text
task -> route -> evidence -> contribution -> decision -> reusable artifact
```

add this short block:

```markdown
First developer-facing handle:

```bash
python scripts/ls_conductor_review_pr.py --base HEAD~1 --head HEAD --json
```

This wraps the existing PR-review trail and role-market artifacts into a Conductor-shaped JSON response.
```

## Required Russian README changes

Near the top Russian navigation area, after the existing line:

```markdown
Впервые здесь? Начните с: [Why Star LS](docs/WHY_STAR_LS.md) · [2-minute route-stability demo](#2-minute-route-stability-demo) · [Contributor matrix](https://github.com/safal207/LS/issues/563)
```

add:

```markdown
Быстрый старт для разработчика: [LS Conductor Quickstart](docs/CONDUCTOR_QUICKSTART.md) · первая CLI-ручка: `python scripts/ls_conductor_review_pr.py --base HEAD~1 --head HEAD --json`
```

## Preserve boundaries

Do not claim:

```text
hosted production API;
formal proof of best answer;
global model ranking;
formal Nash equilibrium;
production compliance.
```

Safe framing:

```text
first developer-facing CLI wrapper over existing LS PR-review route artifacts
```

## Definition of Done

- README top English area links to `docs/CONDUCTOR_QUICKSTART.md`.
- README top Russian area links to `docs/CONDUCTOR_QUICKSTART.md`.
- README contains the first Conductor CLI command near the English first-visitor section.
- No project claims are strengthened.
- No unrelated files are changed.
