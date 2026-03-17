# Market Layer MVP (FastAPI + SQLite)

Исполняемый протокол AI-экономики:

`capital -> task -> execution -> verification -> payout -> reputation -> feedback`

## Что есть в v1

- **Capital/Treasury**: проекты с балансом (`/projects`), публикация задач только при покрытии reward.
- **Task + Bid market**: ставки, ручное назначение и auto-assign по scoring.
- **Execution layer**: реальное исполнение задач через `execute_task` (LLM + fallback), включая use-case `landing_generator`.
- **Verification v2**: staged checks (`auto`, `reviewer`, `impact`).
- **Settlement**: escrow + holdback + scheduler (`/settlement/run`).
- **Reputation**: апдейт по качеству + штраф при dispute.
- **Governance**: runtime-настройка параметров экономики.
- **Ledger**: append-only события для аудита и аналитики.

## Ключевые endpoint'ы

- `POST /projects`, `GET /projects`
- `POST /agents`, `GET /agents`
- `POST /tasks`, `GET /tasks`
- `POST /tasks/{id}/bids`, `GET /tasks/{id}/bids`
- `POST /tasks/{id}/assign`, `POST /tasks/{id}/assign/best`
- `POST /tasks/{id}/execute`, `POST /tasks/{id}/autoloop`
- `POST /tasks/{id}/verify/stage`, `POST /tasks/{id}/verify`
- `POST /tasks/{id}/accept`, `POST /tasks/{id}/dispute`
- `GET /settlements`, `POST /settlement/run`
- `GET /governance`, `POST /governance/{key}`
- `GET /ledger`

## Быстрый запуск

```bash
cd market_layer_mvp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Swagger UI: `http://localhost:8000/docs`

## Landing generator (реальный use-case)

При `use_case=landing_generator` execution-слой создаёт HTML-артефакт с CTA.

Auto-loop:

`task_created -> bids -> assign_best -> execute -> staged verify -> accept -> settlement_run`

## LLM интеграция

- Если задан `OPENAI_API_KEY`, используется OpenAI Chat Completions.
- Если ключа нет — работает deterministic fallback (чтобы контур всегда был исполняем).

## Позиционирование и статус

- `docs/MARKET_LAYER_MVP_4W_RU.md`
- `docs/MARKET_LAYER_MVP_STATUS_RU.md`
