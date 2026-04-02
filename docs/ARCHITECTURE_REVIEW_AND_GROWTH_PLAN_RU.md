# LS / GhostGPT — обзор репозитория, архитектурные улучшения и план развития

## 1) Краткий обзор текущего состояния

Сильные стороны:
- Уже есть разделение на `apps/` (точки входа), `python/modules/` (доменная логика) и `rust_core/` (производительное ядро).
- Есть зрелый слой документации (`docs/ARCHITECTURE.md`, RFC/спеки, roadmap, тестовые планы).
- Есть активный набор тестов для agent/runtime/memory/Web4 направлений.

Главные риски масштаба:
- Дублирование bootstrap-логики в entrypoint'ах (`apps/console/main.py`, `apps/ghostgpt/main.py`) усложняет сопровождение.
- Очень большой и разнородный корень репозитория (несколько параллельных приложений и исторических артефактов), что повышает стоимость онбординга и релизов.
- Нет единого «операционного» документа, связывающего архитектуру, продуктовые треки и монетизацию.

## 2) Что улучшено в этой итерации

### 2.1 Единый bootstrap для приложений

Вынесена общая логика инициализации пути и конфигурации в:
- `python/modules/shared/bootstrap.py`

Эта логика теперь переиспользуется из обоих entrypoint'ов:
- `apps/console/main.py`
- `apps/ghostgpt/main.py`

Эффект:
- меньше дублирования;
- ниже риск расхождения поведения между GUI/Console;
- проще дальнейшая эволюция init-пайплайна (например, DI-контейнер, централизованный telemetry bootstrap).


### 2.2 Runtime Context + Event Bus

Добавлен базовый runtime-контейнер:
- `RuntimeContext` с полями `app_name`, `root`, `config`, `event_bus`, `services`.

`bootstrap_app()` теперь возвращает `RuntimeContext`, что создаёт единый контракт для дальнейшего роста:
- централизованная регистрация сервисов (logger/metrics/memory),
- единая точка расширения runtime и plugin-модели,
- единый event-driven канал между модулями через `EventBus`.
- capability-aware `ServiceRegistry` для контролируемого доступа к сервисам runtime.
- базовый `DynamicModuleLoader` для динамического подключения/отключения модулей без усложнения ядра.
- `RuntimeManifest` (version/features/limits/transport_mode) как основа для versioned runtime профилей.

## 3) Целевая архитектурная эволюция (следующие 2-3 спринта)

### Спринт A — «Стабильное ядро»
1. Ввести явные bounded contexts внутри `python/modules/`:
   - `runtime/` (agent loop, orchestration)
   - `cognitive/` (belief/causal/mission)
   - `interfaces/` (audio/stt/llm/gui adapters)
   - `platform/` (config, observability, resilience)
2. Закрыть прямые импорт-зависимости между контекстами через интерфейсы/протоколы.
3. Добавить architectural tests (import rules), чтобы новые PR не ломали слои.

### Спринт B — «Продуктовая сборка»
1. Стабилизировать публичные API профилей запуска:
   - `console`
   - `ghostgpt`
   - `multi-agent`
2. Добавить единый runtime manifest (фичи, флаги, лимиты, transport mode).
3. Вынести «экспериментальные» модули в отдельный namespace (`labs/`), чтобы не смешивать с production-ядром.

### Спринт C — «Enterprise readiness»
1. Добавить SLA-метрики в observability (latency, error budgets, queue saturation).
2. Ввести capability-based access policy для агентных операций.
3. Подготовить LTS-ветку core API + semver policy для интеграторов.

## 4) План развития продукта

### Этап 1: Developer-first (0-3 месяца)
- Цель: сделать LS удобной платформой для разработчиков локальных агентных систем.
- Артефакты:
  - SDK-гайды,
  - шаблоны интеграции с локальными LLM,
  - reference demo под интервью/ассистента.
- KPI:
  - время «до первого успешного сценария» < 30 минут,
  - рост внешних контрибьюторов и интеграций.

### Этап 2: Team workflows (3-6 месяцев)
- Цель: multi-agent orchestration и память для командных сценариев (R&D, support, sales enablement).
- Артефакты:
  - policy presets,
  - audit trail,
  - federation profile для нескольких инстансов.
- KPI:
  - удержание команд (WAU/MAU),
  - число активных агентных workflow на организацию.

### Этап 3: Regulated verticals (6-12 месяцев)
- Цель: финтех/мед/юридические кейсы с требованиями локальности и аудита.
- Артефакты:
  - compliance pack,
  - deployment blueprints (on-prem/air-gapped),
  - расширенный trust & provenance слой.

## 5) Монетизация: практичная модель

### Модель A — Open Core + Pro Add-ons
- Бесплатно: базовый локальный runtime, базовые коннекторы, базовый memory.
- Платно:
  - advanced observability,
  - policy/governance studio,
  - enterprise connectors,
  - support SLA.

### Модель B — B2B лицензирование platform bundles
- Лицензия на команду/узел для on-prem инсталляций.
- Отдельный прайс на regulated-pack и audit features.

### Модель C — Партнёрская интеграция
- Revenue-share с интеграторами, которые внедряют LS в корпоративные контуры.
- Сертификация партнёров (solution tiers).

Рекомендуемая последовательность:
1. Старт с Open Core + paid support.
2. Затем добавить Pro governance/observability.
3. После product-market fit — enterprise bundles и партнёрскую сеть.

## 6) Что важно сделать прямо сейчас (чеклист фаундера)

1. Зафиксировать продуктовую «единицу ценности»: 
   - «Локальный агентный runtime с долговременной памятью и governance».
2. Выбрать 2 вертикали пилотов (например, HR interview intelligence + internal knowledge ops).
3. Сформировать pricing v0:
   - Free,
   - Team,
   - Enterprise.
4. Подготовить 3 демонстрации ROI (время, качество решений, снижение ошибок).
5. Ввести метрики воронки (activation, retention, expansion).

---

Если нужно, следующим шагом можно сделать отдельный документ `docs/GO_TO_MARKET_RU.md` с ценовыми пакетами, ICP и 90-дневным execution-планом по неделям.
