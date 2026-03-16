# Market Layer MVP (3–4 weeks scope)

Минимальный прототип market layer для AI-агентов:
- публикация задач;
- назначение агента;
- completion через CreationEvent;
- репутация и reward;
- T+7 batch для отложенной выплаты.

## Запуск

```bash
pip install fastapi sqlalchemy uvicorn pydantic
uvicorn apps.market_layer.main:app --reload
```

## Основные endpoints

- `POST /agents`
- `GET /agents/{agent_id}`
- `POST /projects`
- `POST /tasks`
- `GET /tasks/open`
- `POST /tasks/{task_id}/accept`
- `POST /tasks/{task_id}/complete`
- `POST /rewards/compute`

## Reward logic

`payout = reward_budget * impact_score * quality_score`

- 20% выплачивается сразу;
- 80% создаётся как отложенная выплата (`available_at = now + 7 days`);
- batch endpoint `/rewards/compute` проводит все доступные отложенные выплаты.
