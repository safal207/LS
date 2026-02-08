# CIP Runtime Integration Layer (Python ↔ Rust) — Final Issue

## Контекст
CIP остаётся центральным незавершённым узлом Web4‑архитектуры.
Для завершения PR #88 и перехода Phase 4 → Phase 5 требуется рабочий runtime‑слой, который:

- использует Rust‑транспорт (RTT),
- валидирует CIP‑конверты,
- выполняет handshake,
- обновляет TrustFSM,
- маршрутизирует сообщения через ProtocolRouter,
- интегрируется в AgentLoop.

Этот issue формализует полный объём работ.

## Цель
Создать полностью рабочий CIP‑runtime, включающий:

- envelope builder + canonical JSON + подписи,
- envelope validator + error‑model,
- handshake runtime (HELLO → VERIFY → TRUST GATE → STATE_UPDATE → INTENT),
- интеграцию с Rust‑транспортом,
- интеграцию с ProtocolRouter,
- интеграционные тесты,
- smoke‑test CLI.

## 📦 Scope (область работ)

### 1. CIP Envelope Builder
Реализовать модуль, который создаёт корректный CIP‑конверт.

**Требования**
- canonical JSON (`sort_keys=True`, `separators=(",", ":")`)
- подпись Ed25519 (подписывается envelope без блока `sign`)
- верификация подписи
- проверка fingerprint ↔ pubkey
- проверка timestamp (±120 секунд)
- проверка msg_id (UUID v4)
- автоматическое заполнение:
  - `cip: "1.0"`
  - `timestamp`
  - `msg_id`
  - `sender`
  - `trust.sender_view`

**Минимальная схема envelope (нормативная)**
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

### 2. CIP Envelope Validator
Реализовать строгий валидатор.

**Проверки**
- структура envelope
- обязательные поля
- корректность типов
- корректность trust‑state
- корректность state‑блока
- корректность payload‑schema
- подпись
- timestamp
- msg_id

**Error‑model**
```python
class InvalidEnvelopeError(Exception): ...
class SignatureMismatchError(Exception): ...
class TimestampError(Exception): ...
class TrustViolationError(Exception): ...
class PayloadSchemaError(Exception): ...
class TransportError(Exception): ...
```

### 3. CIP Handshake Runtime

**FSM (нормативная)**
```
A → B: HELLO (nonce, challenge)
B → A: HELLO (nonce, signed_challenge)
A → B: VERIFY (signature, fingerprint)
A → B: STATE_UPDATE (presence, lri)
A → B: INTENT (goal)
```

**Требования**
- проверка challenge‑response
- проверка fingerprint
- TrustFSM переходы:
  - untrusted → probing
  - probing → trusted (после VERIFY)
- отправка первого STATE_UPDATE
- отправка INTENT

### 4. Интеграция с Rust‑транспортом (RTT)

**RTT API (Python binding)**
```python
channel = transport.open_channel("control")
transport.send(channel, bytes)
raw = transport.receive(channel)
```

**Требования**
- encode envelope → bytes
- decode bytes → envelope
- validate → route
- retry‑политика при ошибках транспорта
- graceful shutdown

### 5. Интеграция в ProtocolRouter

**Маршруты**
- HELLO → handshake runtime
- VERIFY → TrustFSM
- STATE_UPDATE → Agent state
- FACT_PROPOSE → Knowledge Exchange
- FACT_CONFIRM → DMP‑trace
- FACT_REJECT → dispute handling
- INTENT → intent‑router

### 6. Интеграционные тесты

**Тесты**
- handshake end‑to‑end
- trust transitions
- state update
- fact propose → confirm
- routing correctness

### 7. Smoke‑test CLI

**Файл:** `scripts/cip_demo.py`

**Поведение**
- запускает RTT
- открывает канал
- выполняет HELLO → VERIFY → INTENT
- выводит лог шагов

## 📁 Предлагаемая структура файлов

```
python/cip/envelope.py
python/cip/validator.py
python/cip/handshake.py
python/cip/runtime.py
python/cip/router_adapter.py
scripts/cip_demo.py
tests/integration/testciphandshake.py
tests/integration/testciptrust_transitions.py
```

## 🧪 Тест‑план

**Handshake**
- A и B обмениваются HELLO
- A валидирует challenge‑response
- TrustFSM: untrusted → probing → trusted

**State Update**
- отправка state‑блока
- обновление состояния агента

**Fact propose/confirm**
- проверка payload‑schema
- проверка DMP‑trace

**Routing**
- CIP → Router → subsystem

## ⚠️ Риски и зависимости
- Требуется готовый RTT Python binding
- Требуется актуальная спецификация CIP
- Требуется синхронизация с ProtocolRouter API
