# Merge codex branches and create PR — runbook

Цель: безопасно объединить изменения из рабочих веток `codex/*` в `main` и оформить новый PR с понятным описанием.

## Быстрый сценарий для задачи `codex/merge-codex-branches-and-create-pr`

Используйте этот блок, когда нужно явно объединить изменения из ветки
`codex/merge-codex-branches-and-create-pr`.

```bash
git fetch --all --prune
git checkout main
git pull --ff-only origin main
git checkout -b codex/merge-codex-branches-and-create-pr
# ...внести/проверить изменения...
git checkout main
git merge --no-ff codex/merge-codex-branches-and-create-pr
git push origin main
```

Если ветка уже существует локально, не создавайте её повторно — просто переключитесь
на неё (`git checkout codex/merge-codex-branches-and-create-pr`).

## Шаги (универсальный поток)

1. Обновить локальные ссылки и проверить ветки:
   - `git fetch --all --prune`
   - `git branch -a`
2. Проверить, что целевая ветка основана на актуальном `main`:
   - `git checkout -b codex/<task-name> origin/main`
3. Перенести изменения из source-ветки:
   - `git merge --no-ff <source-branch>`
   - или `git cherry-pick <commit-range>` при выборочном переносе.
4. Разрешить конфликты и запустить минимальные проверки:
   - `pytest -q` (если затронут Python)
   - `cargo test --all --release` (если затронут Rust)
5. Зафиксировать изменения:
   - `git add -A && git commit -m "<scope>: merge <source-branch> into <target-branch>"`
6. Подготовить PR:
   - Чёткий заголовок: что и зачем объединяется.
   - В body: контекст, список изменений, риски, результаты проверок.

## Особенность этого репозитория в текущем снапшоте

В текущем локальном окружении может быть доступна только ветка `work` и отсутствовать
`origin`. В этом случае:

- создайте временную локальную ветку с именем задачи (`git checkout -b codex/<task-name>`),
- выполните merge в `work`,
- подготовьте PR-описание через локальный workflow/инструмент автоматизации.

## Шаблон PR

### Title

`chore(branching): merge <source-branch> into <target-branch>`

### Body

- Context: why this merge is needed now.
- What changed: concise bullet list of merged components.
- Validation: exact commands and outcomes.
- Risk/Rollback: known risks and rollback strategy.

## Definition of done

- Все конфликты разрешены.
- Локальные проверки проходят.
- PR создан с полным описанием и планом отката.
