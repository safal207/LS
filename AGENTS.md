# Что сделано (май 2026)

## E6 Live Model Pilot v0.2 — Multi-Actor
- `scripts/run_live_model_pilot.py` — v0.2: вызывает готовых акторов (Ollama, Gonka, MiMo) с ролями executor/designer/consumer/planner/verifier/risk_critic/approver
- `scripts/run_model_roster_depth_probe.py` — добавлены `_call_ollama_actor()`, `call_actor()`, `build_multi_actor_probe_payload()`
- Route comparison: `route_won_vs_single` — best multi-actor quality vs single answer
- CLI: `--live` для реальных вызовов, `--json` для вывода

## Route Memory v0
- `build_pilot_payload()` подключён к `TrailNetworkBridge` (`python/ls/agent_shell/trail_network.py`)
- При `--live` + победе маршрута: `bridge.submit_contribution()` + `bridge.record_outcome()` → `durable_state_written = True`
- Генерация `route_key = live_model_pilot/{question_hash}>{actor1}>{actor2}...`
- Проверка существующего маршрута через `bridge.recommend_route()` перед повторным опросом акторов
- Поле `route_memory` в payload: version, available, used, route_key, durable_state_written, health

## Landing Update
- `ghostgpt-ls-landing/src/components/NetworkTrajectory.tsx` — добавлены метрики route memory v0 + live pilot v0.2, обновлены тексты (EN + RU)
- `docs/LIVE_MODEL_PILOT.md` — переписан под v0.2, раздел Route Memory
- `docs/NETWORK_PRECISION_CONTRIBUTOR_CALL.md` — добавлены поля route_memory_key, route_memory_persisted, route_memory_health
- Landing собран: `npm install && vite build`

## Исправления тестов
- `test_live_model_pilot.py` — версия v0.1 → v0.2, проверка `multi_actor_route is None`, `route_memory`
- `test_mcp_network_precision_probes.py` — версия v0.1 → v0.2
- Все 14 тестов проходят

## Следующие шаги (на выбор)
- Contributor Pack — один вызов → полный md-отчёт
- MCP ответ — модель шлёт ответ, LS возвращает route score + причины
