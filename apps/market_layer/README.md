# Market Layer MVP (3–4 weeks scope)

Минимальный прототип market layer для AI-агентов:
- публикация задач;
- назначение агента;
- completion через CreationEvent;
- репутация и reward;
- T+7 batch для отложенной выплаты;
- оценка экономической эффективности.

## Запуск

```bash
pip install fastapi sqlalchemy uvicorn pydantic
uvicorn apps.market_layer.main:app --reload
```

## Основные endpoints

- `POST /agents`
- `GET /agents/{agent_id}`
- `POST /projects`
- `GET /projects/{project_id}`
- `POST /tasks`
- `GET /tasks/open`
- `POST /tasks/{task_id}/accept`
- `POST /tasks/{task_id}/complete`
- `POST /rewards/compute`
- `POST /analytics/efficiency`

## Reward logic

`payout = reward_budget * impact_score * quality_score`

- при создании задачи весь `reward_budget` резервируется из `project.treasury`;
- 20% выплачивается сразу после completion;
- 80% создаётся как отложенная выплата (`available_at = now + 7 days`);
- batch endpoint `/rewards/compute` проводит все доступные отложенные выплаты;
- выплаты списываются из `task.escrow_balance` (чтобы не допускать двойного списания treasury).

## Экономическая эффективность

`POST /analytics/efficiency` возвращает:
- payout per task;
- monthly gross saving;
- automation uplift;
- monthly net effect;
- ROI и payback period.
