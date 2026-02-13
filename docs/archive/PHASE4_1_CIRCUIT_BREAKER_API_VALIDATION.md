# Phase 4.1 — Smart Circuit Breaker (Implementation Review + API Validation)

## 0) Контекст
Этот документ фиксирует ревью предлагаемого MVP‑API Circuit Breaker, оценку state‑machine, требования Temporal Foundation, тест‑план и вердикт готовности для PR #1 (CircuitBreaker Core).

---

## 1) Ревью архитектуры предлагаемого API

### Предложенный MVP‑интерфейс
- `CircuitBreakerState` с CLOSED / OPEN / HALF_OPEN.
- `CircuitBreakerConfig` с порогами для отказов, cooldown и half‑open recovery.
- `CircuitBreaker` с методами `before_call()`, `after_success()`, `after_failure()`.

### Корректность и целостность API
**Сильные стороны**
- Минимальный, чётко сфокусированный API.
- Разделение жизненного цикла вызова: `before_call` → `after_success` / `after_failure`.
- Отдельные конфиги позволяют переиспользование в CaPU.

**Риски и пробелы**
1. **Недостаток контекста в `before_call()`**
   - Отсутствует причина блокировки (например, “cooldown_active”).
   - CaPU сложнее будет логировать и метриковать поведение.
2. **Нет явного контракта ошибок**
   - Возврат `bool` ограничивает обработку: нельзя вернуть время до повторной попытки.
3. **Не учитывается адаптивная политика**
   - Нет возможности использовать exponential backoff, jitter или window‑based failure rate.
4. **Нет метода для внешней инспекции**
   - Нужны `current_state()` и/или `snapshot()` для observability.
5. **Нет явного reset/force‑open интерфейса**
   - Практически нужен для тестов и админ‑операций.

### Достаточность для интеграции в CaPU
- **Базово — да**, но нужны расширения для метрик/логирования и безопасной интеграции.
- Не хватает каналов для телеметрии (why‑open, retry‑after, counters).

---

## 2) Проверка state machine (теоретически)

### CLOSED → OPEN
**Ожидается**: после `failure_threshold` подряд.
- Корректно реализовано.
- Edge: нужно сбрасывать failure‑count при успехе в CLOSED.

### OPEN → HALF_OPEN
**Ожидается**: после `recovery_timeout_seconds`.
- Корректно, но нужен guard при `opened_at = None`.
- Важно учитывать монотонность времени.

### HALF_OPEN → CLOSED
**Ожидается**: после `half_open_success_threshold` успешных вызовов.
- Корректно.
- Edge: если `half_open_success_threshold == 0` → immediate close.

### HALF_OPEN → OPEN
**Ожидается**: первая же ошибка открывает.
- Корректно.
- Edge: важно сбросить `_success_count`.

### Критические edge cases
- OPEN без `opened_at` → зависшее состояние.
- Одновременные вызовы (если breaker shared между потоками) → требуются atomic updates.
- Окно между `before_call()` и `after_*()` (в конкурентной среде) может порождать дрейф счётчиков.

---

## 3) Temporal Foundation интеграция

### Хранение `opened_at`
- Лучше хранить как timezone‑aware `datetime` (UTC).
- Для монотонности стоит опционально хранить monotonic timestamp (если доступен), чтобы избегать сдвигов системного времени.

### Расчёт cooldown
- Использовать `now = datetime.now(timezone.utc)`
- `elapsed = (now - opened_at).total_seconds()`
- Важно учитывать корректность при переносе времени.

### Как избежать temporal‑noise
- Минимизировать чтение wall‑clock.
- Использовать единый источник времени (Temporal Foundation), если интеграция добавит timestamp provider.
- Стандартизировать границы сравнения (например, `>= recovery_timeout_seconds`).

### Рекомендации
- Вынести источник времени в dependency injection (`clock` или `time_provider`).
- Для интеграции с Temporal Foundation учитывать rolling windows отказов (опционально).

---

## 4) Тест‑план

### Unit tests (state transitions)
- CLOSED → OPEN after N failures.
- OPEN → HALF_OPEN after cooldown.
- HALF_OPEN → CLOSED after M successes.
- HALF_OPEN → OPEN after 1 failure.

### Edge‑case tests
- OPEN без `_opened_at`.
- cooldown boundary: ровно на границе.
- Success в CLOSED сбрасывает failure count.
- Failure в HALF_OPEN сбрасывает success count.
- multiple transitions in a row.

### Time‑based tests
- Симуляция истечения cooldown.
- Быстрые последовательные фейлы.
- Проверка timezone‑aware timestamps.

### Integration tests (CaPU)
- Подключение breaker к внешнему API.
- Логирование состояния при отказе.
- Проверка корректного блока вызова при OPEN.

---

## 5) Вердикт готовности API

**Вердикт:** **Ready with notes**

API в целом достаточен для старта PR #1, но рекомендуются расширения:
- Методы `current_state()` и `snapshot()`.
- Явный contract на `before_call` (bool vs exception vs status object).
- Внедрение источника времени.

---

## 6) Рекомендации по улучшению API

### Рекомендуемые улучшения
1. `before_call()` → возвращать `BreakerDecision` (allowed, reason, retry_after).
2. `current_state()` для external observability.
3. `reset()` и `force_open()` для админ‑операций.
4. Инъекция `clock` (temporal provider) для deterministic tests.
5. Добавить optional backoff strategy (exponential, jitter).

---

## 7) Список проблем (по severity)

### Critical
- Нет явного канала передачи причины отказа (`before_call` возвращает только bool) → сложно интегрировать в CaPU.

### High
- Отсутствие time‑provider и reliance на wall‑clock → риски при skew/time‑shift.

### Medium
- Нет snapshot/metrics API → невозможность телеметрии.
- Нет backoff strategy → ограниченная расширяемость.

### Low
- Нет admin reset / force open интерфейсов.

### Cosmetic
- Нет явного описания контрактов методов (docstrings).

---

## 8) Финальный вывод
Предложенный MVP‑API соответствует минимальным требованиям, но рекомендуется расширить контракт `before_call` и добавить инструменты наблюдаемости и временной абстракции для устойчивой интеграции в CaPU и Temporal Foundation.
