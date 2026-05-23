# README Star Entry Patch Prompt

Use this prompt with Codex, Claude Code, or another repo-editing agent.

Goal: make the top of `README.md` more attractive and actionable for first-time GitHub visitors, without changing the project claims.

## Patch-only instruction

You are editing the LS repository.

Modify only:

```text
README.md
```

Do not modify code, tests, schemas, workflows, or examples.

## Required README changes

Near the top English navigation area, after:

```text
Positioning: [Project Positioning](docs/PROJECT_POSITIONING.md)
```

add:

```markdown
New here? Start with: [Why Star LS](docs/WHY_STAR_LS.md) · [2-minute route-stability demo](#2-minute-route-stability-demo) · [Contributor matrix](https://github.com/safal207/LS/issues/563)
```

After the `## First 10 seconds` section opening explanation and before the longer demo list, add this compact block:

```markdown
### 2-minute route-stability demo

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
python scripts/run_nash_route_stability_demo.py --json
```

This checks the current route-stability evidence chain:

```text
schema
-> checked-in sample
-> negative fixtures
-> deterministic probe
-> regression test
-> explicit non-claims
```

Want to help? Try the [contributor matrix](https://github.com/safal207/LS/issues/563): run the same bounded probe on your OS, model runtime, and hardware.
```

Near the Russian navigation area, after:

```text
Позиционирование: [Project Positioning](docs/PROJECT_POSITIONING.md)
```

add:

```markdown
Впервые здесь? Начните с: [Why Star LS](docs/WHY_STAR_LS.md) · [2-minute route-stability demo](#2-minute-route-stability-demo) · [Contributor matrix](https://github.com/safal207/LS/issues/563)
```

## Preserve boundaries

Do not claim:

```text
formal Nash equilibrium;
global model ranking;
global contributor ranking;
statistical sufficiency;
production-grade governance.
```

Keep this boundary if mentioned:

```text
Nash-style route stability proxy, not a formal proof of Nash equilibrium.
```

## Definition of Done

- `README.md` contains a visible `Why Star LS` link near the top.
- `README.md` contains a direct link to issue #563 near the top.
- `README.md` contains a compact 2-minute demo block.
- English and Russian entry areas both contain a first-visitor path.
- No project claims are strengthened.
- No unrelated files are changed.
