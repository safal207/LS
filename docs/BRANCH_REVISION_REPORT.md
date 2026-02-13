# Web4 Runtime — Branch Revision Report

Дата ревизии: 2026-02-13

## Ограничения среды

В текущем локальном git-клоне доступна только ветка `work`; remotes и полный удалённый список веток не настроены. Поэтому таблица ниже разделена на:

1. **Наблюдаемые ветки** (точно доступны локально).
2. **Исторические ветки (inferred)** — восстановлены по merge-коммитам в `git log --all`.

## 1) Наблюдаемые ветки

| Ветка | Статус | Что содержит | Что делать |
|---|---|---|---|
| work | active | Текущий интегрированный state после PR #110 (QoS, Lifecycle, Multi-Transport, CI sync) | оставить как рабочую ветку; держать в синхронизации с основной интеграционной веткой |

## 2) Исторические ветки (inferred из merge history)

| Ветка | Статус | Что содержит | Что делать |
|---|---|---|---|
| codex/prepare-pr-plan-for-6.1 | merged | QoS, lifecycle hooks, multi-transport, hotfix 6.3.1 | считать завершённой и закрытой |
| codex/update-codex_tasks.md-status | merged | обновление статусов задач и веточной модели | оставить в истории, не восстанавливать |
| codex/add-api-parity-contract-tests | merged | API parity тесты Python↔Rust | завершено |
| codex/add-health-metrics-to-rust_bridge.py | merged | health metrics + fallback logging | завершено |
| codex/add-tests-for-pythonrust-bridge | merged | тесты rust bridge | завершено |
| codex/expand-python-ci-in-workflow | merged | расширение CI на python подсистемы | завершено |
| codex/create-formal-task-list-for-codex | merged | формализация backlog/тасков | завершено |
| codex/fix-pyo3-ci-linking-issue | merged | фиксы линковки PyO3 в CI | завершено |
| codex/analyze-current-state-of-main-branch | merged | отчёт о состоянии ветки | контент сохранён в docs |
| codex/create-new-pr-for-add-automatic-ruff-autofix-job | merged | workflow автофикса | завершено |
| codex/merge-ruff-autofix-workflow-into-main | merged | добавление autofix workflow | завершено |
| codex/create-autonomous-execution-plan-for-codex | merged | генераторы и ранние execution планы runtime/mesh/platform | исходные планы перенесены в `docs/archive/` |

## Рекомендации по удалению веток

С учётом локально доступных данных, **к удалению рекомендованы все исторические `codex/*` ветки, уже влитые через PR**, если они ещё существуют на remote.

Минимальный набор веток, который стоит оставлять:

- `main` (или другой canonical integration branch в remote)
- `work` (локальная рабочая, если используется)
- активные feature-ветки с незавершёнными задачами (при наличии)

