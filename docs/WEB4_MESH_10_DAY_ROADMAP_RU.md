# Web4 Mesh: дорожная карта на 10 дней (LS-native)

## Зачем это для LS
Web4 Mesh в LS — это не просто сетевой слой, а **когнитивная ткань** между агентами:
- сообщения идут в формате envelope-first,
- доверие регулируется через FSM,
- наблюдаемость встроена как first-class сигнал,
- синхронизация памяти делается chunk-обменом, а не «сырыми» дампами.

Именно такой подход сохраняет уникальную философию проекта: *рефлексия + доверие + управляемая эволюция поля*.

## Цель
За 10 дней получить минимально рабочую mesh-сеть из 3–5 нод, которая:
1. обнаруживает соседей,
2. распространяет рефлексии,
3. синхронизирует когнитивный граф,
4. дает операционные сигналы в observability.

## Definition of Done
1. Поднимаются минимум 3 ноды в локальном окружении.
2. Рефлексия, созданная на одной ноде, доходит до остальных и не дублируется.
3. Поздно вошедшая нода догоняет граф через `SYNC_GRAPH_REQUEST`/`SYNC_GRAPH_CHUNK`.
4. Есть базовая проверка доверия (trust state transitions) и журнал событий.
5. Есть smoke-сценарий запуска (одна команда) и тесты.

## Что уже реализовано в репозитории (на старте roadmap)
- `Web4MeshNode` с типами сообщений:
  - `ANNOUNCE`
  - `PUSH_REFLECTION`
  - `SYNC_GRAPH_REQUEST`
  - `SYNC_GRAPH_CHUNK`
- dedup envelope/reflection,
- trust-aware receive pipeline,
- observability события по ключевым действиям,
- опциональная подпись/верификация payload,
- unit-тесты на discovery, broadcast, sync и подписи.

## План по дням

### Дни 1–3 — устойчивое ядро
- [x] Узел `Web4MeshNode` и базовые message handlers.
- [x] Envelope/reflection dedup + chunk-limit.
- [x] Trust + observability hooks.
- [x] Unit-тесты на happy path + edge cases.
- [ ] Прототип docker-compose для 3 нод.

### Дни 4–6 — transport и реальная связность
- [ ] Подключить transport-адаптер (начать с websocket/asyncio, затем libp2p bridge).
- [ ] Ввести gossip-топик для `PUSH_REFLECTION`.
- [ ] Добавить discovery (DHT/peer registry adapter).
- [ ] Добавить подпись ed25519 с ротацией ключей и trust-policy на verify fail.

### Дни 7–10 — demo-ready и операционка
- [ ] Прогон 5 нод на разных портах.
- [ ] Метрики: online peers, sync latency, message rate, duplicate drop rate.
- [ ] Скрипт `run_mesh.sh` / `make run-mesh` («поднять сеть за 30 секунд»).
- [ ] README: quickstart + troubleshooting + expected telemetry.

## Технические интеграции внутри LS
1. **Trust слой**: `DistributedTrustFSM` — для gatekeeping входящих envelope.
2. **Observability слой**: `MeshObservabilityHub` — для event trail и диагностики.
3. **Graph слой**: `memory_graph` как минимальный shared cognitive context.
4. **Runtime перспектива**: следующий шаг — связать node с transport backend из runtime-модулей.

## Следующий шаг (сегодня)
1. Поднять 3 процесса (A/B/C) на локальном transport.
2. Прогнать сценарий:
   - A публикует reflection,
   - B/C принимают,
   - D входит позже и делает sync request.
3. Зафиксировать SLA-метрики (latency, duplicate ratio, sync completeness) в отдельном отчете.
