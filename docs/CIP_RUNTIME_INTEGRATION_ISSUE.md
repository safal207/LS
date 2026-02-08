# Web4 Runtime Integration Milestone — Full Stack Implementation (Final)

## Контекст
LS находится на критическом рубеже Phase 4 → Phase 5. Для закрытия PR #88 требуется единый, исчерпывающий milestone‑документ, который задаёт полный контракт на интеграцию RTT, CIP, HCP, LIP, ProtocolRouter, TrustFSM и AgentLoop, а также фиксирует требования к наблюдаемости, тестам и CLI‑демо.

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

## ✅ Definition of Done
- RTT, CIP, HCP, LIP работают в связке через ProtocolRouter и AgentLoop.
- Handshake‑процедуры и TrustFSM переходы воспроизводимы и детерминированы.
- Все интеграционные тесты и CLI‑демо проходят локально.
- Наблюдаемость покрывает ключевые события (handshake, trust, routing, errors).

## 🚦 Порядок запуска (Execution Plan)

### Этап 1 — Базовый транспорт и трассировка
- [ ] Реализовать RTT handshake + каналы control/state/knowledge.
- [ ] Добавить минимальный event sink (RTT telemetry + errors).
- [ ] Подготовить mock‑transport для тестов.

### Этап 2 — CIP ядро
- [ ] Envelope builder (canonical JSON + подпись Ed25519).
- [ ] Envelope validator + error‑model.
- [ ] Handshake runtime + TrustFSM переходы.
- [ ] Простейшая маршрутизация CIP → ProtocolRouter.

### Этап 3 — HCP/LIP рантаймы
- [ ] HCP базовые события + consent/pacing.
- [ ] LIP базовые события + deferred acceptance.
- [ ] Связка HCP/LIP с ProtocolRouter.

### Этап 4 — AgentLoop + Observability
- [ ] Интеграция событий в AgentLoop.
- [ ] Полный event contract v1.0.
- [ ] Логи trust/handshake/state/knowledge.

### Этап 5 — Тесты и CLI демо
- [ ] Интеграционные тесты CIP/HCP/LIP/RTT.
- [ ] scripts/web4_demo.py.
- [ ] scripts/web4meshdemo.py.

## 📦 Scope (область работ)

### 1. RTT Runtime Layer (Rust ↔ Python)
**Реализовать**
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
transport.close_channel(channel)
transport.shutdown()
```

**Error‑model (RTT)**
```python
class RTTHandshakeError(Exception): ...
class RTTTransportError(Exception): ...
class RTTBackpressureError(Exception): ...
class RTTReplayError(Exception): ...
```

### 2. CIP Runtime Layer (Python ↔ Rust)
**Реализовать**
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

**Нормативный envelope (минимум)**
```json
{
  "cip": "1.0",
  "msg_id": "uuid",
  "type": "HELLO | INTENT | FACTPROPOSE | FACTCHALLENGE | FACTCONFIRM | FACTREJECT | DECISIONSHARE | STATEUPDATE",
  "timestamp": "RFC3339",
  "sender": {
    "agent_id": "string",
    "fingerprint": "hex",
    "capabilities": ["string"],
    "pubkey": "base64"
  },
  "receiver": {
    "agent_id": "string",
    "fingerprint": "hex"
  },
  "trust": {
    "sender_view": "untrusted | probing | trusted | blacklisted",
    "receiver_view": "unknown | untrusted | probing | trusted | blacklisted"
  },
  "state": {
    "presence": "focused | diffuse | overloaded | engaged",
    "lri": 0,
    "kernel_signals": ["string"],
    "intent": "string"
  },
  "payload": {},
  "sign": {
    "algo": "ed25519",
    "signature": "base64"
  }
}
```

**Error‑model (CIP)**
```python
class InvalidEnvelopeError(Exception): ...
class SignatureMismatchError(Exception): ...
class TimestampError(Exception): ...
class TrustViolationError(Exception): ...
class PayloadSchemaError(Exception): ...
```

### 3. HCP Runtime Layer (Human ↔ Agent)
**Реализовать**
- HCP envelope builder
- human‑state vector (presence, affect, clarity, pressure, consent)
- consent gating
- pacing rules
- HCP_INTENT
- HCP_DECISION
- HCP_FEEDBACK
- integration with AgentLoop

**Минимальные события**
- HCP_HELLO
- HCP_INTENT
- HCP_DECISION
- HCP_FEEDBACK

### 4. LIP Runtime Layer (Internet ↔ Agent)
**Реализовать**
- LIP_FETCH
- LIP_EVIDENCE
- LIP_CONFLICT
- LIP_ACCEPT/REJECT
- deferred acceptance queue
- source trust tiers
- cross‑agent corroboration

**Минимальные события**
- LIP_FETCH
- LIP_EVIDENCE
- LIP_CONFLICT
- LIP_ACCEPT
- LIP_REJECT

### 5. ProtocolRouter (Unified Web4 Router)
**Реализовать**
- CIP routing
- HCP routing
- LIP routing
- TrustFSM updates
- DMP‑trace updates
- Knowledge Exchange
- State updates
- Intent routing

**Routing matrix (минимум)**
- CIP.HELLO → Handshake
- CIP.VERIFY → TrustFSM
- CIP.STATEUPDATE → Agent state
- CIP.FACTPROPOSE → Knowledge Exchange
- HCP.INTENT → AgentLoop
- LIP.EVIDENCE → Knowledge Exchange

### 6. TrustFSM Integration
**Реализовать**
- переходы: untrusted → probing → trusted → blacklisted
- правила эскалации/деградации
- протоколирование всех trust‑событий

### 7. AgentLoop Integration
**Добавить**
- CIP/HCP/LIP events → AgentLoop
- presence/lri updates
- intent propagation
- cognitive cycle hooks
- mission drift detection
- causal memory updates

### 8. Observability Layer (Web4 Events)
**Добавить**
- event sink for CIP/HCP/LIP
- event contract v1.0
- RTT telemetry
- trust transitions
- handshake logs
- state updates
- knowledge exchange logs

### 9. End‑to‑End Tests
**Создать**

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

### 10. CLI Tools

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
