# План исправлений: Race Conditions, аномалии и оптимизации

## Цели
- Убрать критические гонки данных в голосовом конвейере (Audio → STT → LLM).
- Стабилизировать многопоточную работу GUI и мониторинга.
- Закрыть security/operational риски (секреты, автозапуск, предсказуемый fallback).
- Снизить latency и память под реальную нагрузку.

## Область работ
- `audio_module.py`, `stt_module.py`, `llm_module.py`, `ghost_gui.py`, `config.py`, `.gitignore`, `rust_core/*`, `utils.py`.
- Процессные/архитектурные изменения: in-memory pipeline, bounded queues, thread-safe state, secrets via env.

---

## Пошаговый план (по приоритету)

### Этап 1 — Критические гонки (P0)

| ID | Проблема | Изменение | Критерий готовности |
|---|---|---|---|
| RC-01 | TOCTOU на temp audio files | Убрать disk temp-path из hot path. Передавать PCM16/float32 chunks через `queue.Queue` in-memory (`bytes`/`numpy.ndarray`). | Нет `FileNotFoundError`/`PermissionError` на чанках, STT обрабатывает 100% доставленных сегментов. |
| RC-03 | Неограниченная очередь STT→LLM | Ввести `Queue(maxsize=1)` + policy `drop-oldest` (важен последний вопрос). | Размер очереди стабилен (<=1), OOM/накопление отсутствуют. |

**Результат этапа:** конвейер перестаёт терять чанки и «захлёбываться» при медленном LLM.

### Этап 2 — Высокий приоритет (P1)

| ID | Проблема | Изменение | Критерий готовности |
|---|---|---|---|
| RC-02 | Гонка состояния backend (`USE_CLOUD_LLM`) | Заменить mutable-флаг в конфиге на runtime-state (`threading.Event`/state object) внутри LLM-сервиса. | Переключение backend атомарно и наблюдаемо во всех потоках. |
| BUG-04 | Обновление Qt UI не из GUI-thread | Все UI-обновления через `pyqtSignal`/`QMetaObject.invokeMethod(..., Qt.QueuedConnection)`. | Нет warning/crash при стресс-тесте с быстрым потоком сообщений. |
| BUG-02 | Секреты в коде (`GROQ_API_KEY`) | Перенос в `.env`, загрузка через `python-dotenv`, обновление `README` + `.env.example`. | В репо нет рабочих секретов; локальный запуск без правки кода. |

**Результат этапа:** предсказуемый fallback, потокобезопасный GUI, безопасная конфигурация.

### Этап 3 — Средний приоритет (P2)

| ID | Проблема | Изменение | Критерий готовности |
|---|---|---|---|
| RC-04 | RAM monitor shared state | Ввести `threading.Lock` (или lock-free snapshot pattern) для shared метрик. | Метрики консистентны, нет частично обновлённых значений. |
| BUG-01 | VAD reset race | Перевести state machine VAD на атомарные переходы: capture→finalize→reset в одном критическом участке. | Нет смешивания хвоста старой и новой фразы. |
| BUG-05 | Rust/PyO3 GIL + silent autostart | Проверить GIL contract на границе Python↔Rust, добавить explicit user consent на autostart. | Нет deadlock-сценариев, автозапуск только после подтверждения пользователя. |

**Результат этапа:** стабильность под длительной сессией и снижение операционных рисков.

### Этап 4 — Низкий приоритет/перфоманс (P3)

| ID | Проблема | Изменение | Критерий готовности |
|---|---|---|---|
| OPT-02 | Медленный STT профиль | `faster-whisper` с `compute_type="int8"` (и профиль под CPU). | Снижение p95 latency STT (целевой ориентир: ~1.3–1.8x). |
| OPT-03 | Блокирующий LLM HTTP | Перейти на streaming-ответ (`stream=True`) и ранний вывод токенов. | Сокращение time-to-first-token. |
| OPT-04 | `__pycache__` в git | Добавить `__pycache__/` и `*.py[cod]` в `.gitignore`; почистить индекс. | Нет бинарного мусора в диффах/коммитах. |

---

## Что это даст (ожидаемый эффект)

| Категория эффекта | До | После | Практическая польза |
|---|---|---|---|
| Надёжность Audio→STT | Потеря чанков из-за удаления temp-файла до чтения | In-memory передача, отсутствие TOCTOU | Меньше пропусков распознавания и «обрывов» речи |
| Устойчивость STT→LLM | Очередь растёт без лимита при медленном LLM | `maxsize=1`, drop-oldest | Нет memory bloat, ответы релевантнее текущему вопросу |
| Консистентность fallback LLM | Неформализованный глобальный флаг | Явный thread-safe runtime-state | Прозрачное и предсказуемое переключение backend |
| Стабильность GUI | Риск cross-thread обновлений | Сигналы/queued invocation | Уход от undefined behavior и случайных падений UI |
| Безопасность секретов | Ключ может попасть в git history | `.env` + пример + документация | Меньше риск утечки API-ключей |
| Наблюдаемость ресурсов | Возможны неконсистентные метрики RAM | Блокировки или snapshot-модель | Корректные алерты и диагностика под нагрузкой |
| Производительность STT | Избыточный I/O и более тяжёлый compute path | In-memory + int8 | Ниже задержка и выше throughput на CPU |
| UX ответа LLM | Пользователь ждёт полный ответ | Streaming токенов | Быстрее «ощущаемый» отклик |
| Гигиена репозитория | Технический мусор в Git | Чистый `.gitignore` | Проще ревью и меньше шум в PR |

---

## Рекомендуемый порядок PR
1. **PR-1:** In-memory audio pipeline + bounded queue STT→LLM.
2. **PR-2:** Thread-safe LLM backend state + GUI thread-safety.
3. **PR-3:** Secrets management + Rust consent/GIL audit.
4. **PR-4:** Monitoring/VAD fixes + cleanup/perf tweaks.

## Метрики приёмки (Definition of Done)
- Нет ошибок чтения temp audio в логах за 30 минут стресс-теста.
- Размер STT→LLM очереди не превышает 1.
- p95 STT latency и TTFT LLM измерены до/после и улучшены.
- Нет прямых обновлений Qt-виджетов из фоновых потоков.
- В репозитории отсутствуют реальные API keys.
