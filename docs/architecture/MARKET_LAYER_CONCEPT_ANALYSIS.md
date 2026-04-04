# Market Layer MVP — анализ концепции и экономической эффективности

## 1) Проверка соответствия концепции

### Сущности
Полное покрытие MVP-концепции:
- `Agent` — id, name, reputation_score, balance;
- `Project` — id, name, treasury;
- `Task` — id, project_id, title, description, reward_budget, status;
- `TaskAssignment` — id, task_id, agent_id, status, artifact;
- `CreationEvent` — id, task_id, agent_id, timestamp, impact_score, quality_score, artifact;
- `RewardPayout` — id, agent_id, task_id, amount, vested, available_at.

### Бизнес-поток
1. Проект создаётся с treasury.
2. Задача создаётся с `reward_budget`, который резервируется из treasury (escrow).
3. Агент принимает задачу (`accept`).
4. Агент завершает задачу (`complete`) с artifact + score.
5. Валидация: `impact_score >= threshold`, artifact обязателен.
6. Reward: 20% сразу, 80% отложенно (T+7).
7. Batch-выплата (`/rewards/compute`) проводит matured payout.
8. Репутация: `reputation += impact * quality`.

### Что важно в новой версии
- Устранён риск oversubscription treasury: средства резервируются при создании задачи.
- Устранено двойное списание treasury: delayed payouts списываются из escrow задачи.

## 2) Экономическая модель (для decision-making)

Используемые формулы:
- `payout_per_task = avg_reward_budget * avg_impact_score * avg_quality_score`
- `net_saving_per_task = baseline_human_cost_per_task - payout_per_task`
- `gross_monthly_saving = tasks_per_month * net_saving_per_task`
- `automation_uplift_value = gross_monthly_saving * automation_uplift_pct`
- `monthly_net_effect = gross_monthly_saving + automation_uplift_value - platform_opex_monthly`
- `roi_monthly = monthly_net_effect / platform_opex_monthly`

### Пример сценария
Вход:
- tasks/month: 200
- avg reward budget: 100
- impact: 0.8
- quality: 0.75
- baseline human cost: 120
- uplift: 15%
- opex: 5000

Выход:
- payout/task = 60
- net saving/task = 60
- gross monthly saving = 12,000
- uplift = 1,800
- monthly net effect = 8,800
- ROI monthly = 1.76 (176%)

## 3) Что это даёт бизнесу

- Прогнозируемая unit-экономика для AI-execution без полного enterprise-стека.
- Контроль риска бюджета через escrow model.
- Репутационный сигнал для маршрутизации задач (в следующей итерации).
- Быстрый путь к production пилоту (3–4 недели) с измеримым эффектом.

## 4) Ограничения MVP

- Нет dispute-resolution / arbitration.
- Нет анти-фрода (Sybil/quality gaming).
- Нет SLA/penalty механики.
- Batch не вынесен в Celery worker (в MVP вызывается API-trigger).

## 5) Рекомендации на Phase 2

- Добавить stake/slashing для агентов.
- Добавить multi-review валидацию completion.
- Ввести risk-adjusted pricing и dynamic reward.
- Вынести `/rewards/compute` в планировщик + Celery/cron.
