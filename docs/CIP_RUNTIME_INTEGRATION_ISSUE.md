# CIP Runtime Integration Layer (Python ↔ Rust) — Issue Draft

## Контекст
CIP остаётся центральным незавершённым узлом: runtime‑интеграция, валидация конвертов, handshake и маршрутизация через ProtocolRouter пока не доведены до состояния MVP. Этот issue формализует следующий шаг для закрытия PR #88 и завершения перехода Phase 4 → Phase 5.

## Цель
Построить рабочий CIP‑runtime, который:
- использует Rust‑транспорт (RTT);
- валидирует CIP‑envelope по спецификации;
- выполняет handshake и TrustFSM‑гейтинг;
- маршрутизирует сообщения через ProtocolRouter;
- интегрируется в AgentLoop;
- имеет интеграционные тесты и smoke‑test CLI.

## Область работ (Scope)
1. **CIP envelope builder**
   - canonical JSON;
   - подпись, верификация подписи;
   - проверка fingerprint;
   - проверка timestamp;
   - проверка msg_id;
   - формирование envelope‑метаданных.

2. **CIP envelope validator**
   - структура и обязательные поля;
   - тип сообщения и trust‑state;
   - state‑block;
   - payload‑schema;
   - нормализация и отказоустойчивые ошибки.

3. **CIP handshake runtime**
   - HELLO → HELLO;
   - VERIFY → TRUST GATE;
   - STATE_UPDATE;
   - INTENT;
   - интеграция с TrustFSM.

4. **Интеграция с Rust‑транспортом**
   - Python binding: `open_channel("control")`;
   - отправка/получение envelope;
   - decode → validate → route;
   - контроль ошибок и retry‑политики.

5. **Интеграция в ProtocolRouter**
   - CIP → TrustFSM;
   - CIP → StateUpdate;
   - CIP → DMP‑trace;
   - CIP → Knowledge Exchange.

6. **Интеграционные тесты**
   - handshake;
   - state update;
   - fact propose → confirm;
   - trust transitions.

7. **Smoke‑test CLI**
   - `python scripts/cip_demo.py`;
   - базовый маршрут: open → hello → verify → intent.

## Acceptance Criteria
- [ ] Envelope builder создаёт канонический JSON и подпись, пригодную для верификации на стороне runtime.
- [ ] Validator отклоняет некорректные CIP‑конверты с диагностируемыми ошибками.
- [ ] Handshake реализует полный маршрут HELLO → VERIFY → TRUST GATE → STATE_UPDATE → INTENT.
- [ ] ProtocolRouter маршрутизирует валидные CIP‑сообщения в соответствующие подсистемы.
- [ ] RTT канал используется для send/receive сообщений CIP.
- [ ] Интеграционные тесты покрывают handshake и trust‑переходы.
- [ ] `scripts/cip_demo.py` проходит без ошибок на локальной среде.

## Предлагаемая структура файлов
> Пример: подстройте под фактическую структуру репозитория.

- `python/cip/envelope.py`
- `python/cip/validator.py`
- `python/cip/handshake.py`
- `python/cip/runtime.py`
- `python/cip/router_adapter.py`
- `scripts/cip_demo.py`
- `tests/integration/test_cip_handshake.py`
- `tests/integration/test_cip_trust_transitions.py`

## Скелет API (черновик)
```python
class CIPEnvelope:
    def build(self, payload: dict, metadata: dict) -> dict:
        """Create canonical JSON envelope and sign it."""

class CIPValidator:
    def validate(self, envelope: dict) -> None:
        """Raise on invalid structure/signature/state."""

class CIPHandshakeRuntime:
    def run(self, channel) -> None:
        """Perform HELLO → VERIFY → TRUST GATE → STATE_UPDATE → INTENT."""

class CIPRuntime:
    def open(self, transport, channel_name: str = "control") -> None:
        """Open RTT channel and start runtime loop."""
```

## Тест‑план (черновик)
- **Handshake**: имитация обмена HELLO и VERIFY; проверка TrustFSM‑переходов.
- **State Update**: отправка валидного state‑block и проверка маршрутизации.
- **Fact propose/confirm**: проверка соответствия payload‑schema и state‑изменений.
- **Routing**: проверка маршрута CIP → Router → DMP/Knowledge Exchange.

## Риски и зависимости
- Зависимость от готовности RTT Python binding.
- Требуется актуальная спецификация CIP‑envelope и TrustFSM.
- Необходима синхронизация с ProtocolRouter интерфейсом.
