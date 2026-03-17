# Market Layer MVP (FastAPI + SQLite)

Минимальный исполняемый Market Layer с полным циклом:

`task -> bid/assign -> artifact -> verification -> settlement -> reputation -> ledger`

## Что реализовано на текущем этапе

- Task Market + Bid Market (`/tasks`, `/tasks/{id}/bids`, `/tasks/{id}/assign`, `/tasks/{id}/assign/best`)
- Verification v2 (staged checks: auto/reviewer/impact)
- Escrow + holdback + scheduled settlement (`/settlements`, `/settlement/run`)
- Reputation updates + dispute penalty
- Treasury per project (`/projects`)
- Governance parameters (`/governance`, `/governance/{key}`)
- Append-only ledger (`/ledger`)

## Запуск

```bash
cd market_layer_mvp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Swagger UI: `http://localhost:8000/docs`

## Быстрый сценарий

1. `POST /projects` — создать проект с treasury
2. `POST /agents` — создать агентов
3. `POST /tasks` — открыть задачу (резервируется reward из treasury)
4. `POST /tasks/{id}/bids` — подать ставки
5. `POST /tasks/{id}/assign/best` — авто-выбор победителя по auction scoring
6. `POST /tasks/{id}/deliver` — доставка артефакта
7. `POST /tasks/{id}/verify/stage` — staged verification (auto + reviewer + impact)
8. `POST /tasks/{id}/accept` — immediate payout + schedule holdback
9. `POST /settlement/run` — релиз отложенных выплат
10. `GET /ledger` — аудит событий

## Governance параметры

По умолчанию:

- `holdback_rate = 0.2`
- `holdback_days = 7`
- `auction_weight_price = 0.5`
- `auction_weight_rep = 0.3`
- `auction_weight_speed = 0.2`
- `rollback_penalty = 0.15`

Изменение параметра:

`POST /governance/{key}` с `{ "value": <float> }`

## Документация позиционирования

- `docs/MARKET_LAYER_MVP_4W_RU.md`
- `docs/MARKET_LAYER_MVP_STATUS_RU.md`
