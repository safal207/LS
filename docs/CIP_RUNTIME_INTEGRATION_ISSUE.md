# Web4 Runtime Integration Milestone — Full Stack Implementation

## Контекст
LS выходит на критический рубеж Phase 4 → Phase 5. Для закрытия PR #88 и перехода к рабочему Web4‑стеку требуется единый milestone‑документ, описывающий интеграцию RTT, CIP, HCP, LIP, ProtocolRouter, TrustFSM и AgentLoop, а также тесты, CLI‑демо и наблюдаемость.

## 🎯 Цель milestone
Построить полностью рабочий Web4 Runtime, включающий:

- RTT (Rust Transport Tunnel)
- CIP Runtime (agent ↔ agent cognition exchange)
- HCP Runtime (human ↔ agent mediation)
- LIP Runtime (internet learning)
- ProtocolRouter
- TrustFSM
- AgentLoop integration
- Observability
- End‑to‑End tests
- CLI tools

## 📦 Scope (область работ)

### 1. RTT Runtime Layer (Rust ↔ Python)
Реализовать:

- secure p2p handshake
- multiplexed channels (state, knowledge, control)
- heartbeat + reconnect
- replay protection
- Python binding via pyo3
- async runtime loop
- backpressure + queue limits
- error model

**API (Python)**
```python
channel = transport.open_channel("control")
transport.send(channel, bytes)
raw = transport.receive(channel)
```

### 2. CIP Runtime Layer (Python ↔ Rust)
Реализовать:

- envelope builder
- canonical JSON
- Ed25519 signatures
- envelope validator
- handshake runtime
- TrustFSM transitions
- routing into ProtocolRouter
- state update
- fact propose/confirm
- DMP‑trace integration

### 3. HCP Runtime Layer (Human ↔ Agent)
Реализовать:

- HCP envelope builder
- human‑state vector (presence, affect, clarity, pressure, consent)
- consent gating
- pacing rules
- HCP_INTENT
- HCP_DECISION
- HCP_FEEDBACK
- integration with AgentLoop

### 4. LIP Runtime Layer (Internet ↔ Agent)
Реализовать:

- LIP_FETCH
- LIP_EVIDENCE
- LIP_CONFLICT
- LIP_ACCEPT/REJECT
- deferred acceptance queue
- source trust tiers
- cross‑agent corroboration

### 5. ProtocolRouter (Unified Web4 Router)
Реализовать:

- CIP routing
- HCP routing
- LIP routing
- TrustFSM updates
- DMP‑trace updates
- Knowledge Exchange
- State updates
- Intent routing

### 6. AgentLoop Integration
Добавить:

- CIP/HCP/LIP events → AgentLoop
- presence/lri updates
- intent propagation
- cognitive cycle hooks
- mission drift detection
- causal memory updates

### 7. Observability Layer (Web4 Events)
Добавить:

- event sink for CIP/HCP/LIP
- event contract v1.0
- RTT telemetry
- trust transitions
- handshake logs
- state updates
- knowledge exchange logs

### 8. End‑to‑End Tests
Создать:

**CIP tests**
- handshake
- trust transitions
- fact propose/confirm
- routing

**HCP tests**
- consent gating
- pacing rules
- human‑state updates

**LIP tests**
- deferred acceptance
- conflict resolution
- corroboration

**RTT tests**
- handshake
- reconnect
- multiplexing
- queue limits

### 9. CLI Tools

**scripts/web4_demo.py**
- запускает два агента
- RTT handshake
- CIP handshake
- HCP intent
- LIP fetch
- выводит все события

**scripts/web4meshdemo.py**
- 3+ агентов
- mesh routing
- trust propagation
- knowledge consensus

## 📁 Предлагаемая структура файлов

```
python/
  cip/
  hcp/
  lip/
  rtt/
  router/
  trust/
  runtime/
  agent/
scripts/
  web4_demo.py
  web4meshdemo.py
tests/
  integration/
    testcip*.py
    testhcp*.py
    testlip*.py
    testrtt*.py
    testrouter*.py
    testagentloop*.py
```

## 🧪 Acceptance Criteria

- RTT работает стабильно 24 часа
- CIP handshake проходит без ошибок
- TrustFSM корректно обновляется
- HCP соблюдает consent/pacing
- LIP выполняет deferred acceptance
- ProtocolRouter маршрутизирует все типы сообщений
- AgentLoop получает и обрабатывает Web4 события
- Все интеграционные тесты проходят
- CLI демо работает

## ⚠️ Риски

- сложность синхронизации RTT ↔ CIP
- необходимость строгой canonical JSON
- необходимость корректной подписи/валидации
- необходимость async runtime
- необходимость согласованности между протоколами
