# WEB4 Roadmap (Unified)

Этот документ — единый источник истины по состоянию roadmap для Web4 Runtime и связанных направлений (Mesh/Graph/Platform).

## 1. Завершённые этапы

- **6.1 Runtime hardening**: backpressure политики RTT, QoS-метрики, lifecycle hooks, safety/hotfix улучшения.
- **6.2 Protocol-runtime integration**: CIP/HCP/LIP runtime интеграции и router path.
- **6.3 Multi-transport foundation**: абстракция транспорта, registry и transport-agnostic session слой.
- **6.3.1 Hotfix/Docs sync**: lifecycle/QoS корректировки, cleanup документации, архивирование legacy-планов.
- **CI/Quality sync**: ruff/mypy/pytest контуры для web4 модулей, autofix workflow, API parity и bridge test coverage.

## 2. Текущий этап

- **6.3.1 Docs & Repo Sync**
  - синхронизация документации runtime lifecycle/QoS/multi-transport;
  - ревизия веток по merge history;
  - перенос устаревших execution/phase планов в `docs/archive/`;
  - выравнивание roadmap в единый документ.

## 3. Следующий этап

- **6.4 Runtime Consolidation**
  - унификация runtime observability по transport backends;
  - контрактные тесты на transport interchangeability;
  - документирование migration-guide от RTT-specific path к fully transport-agnostic path;
  - расширение CI до более широкого regression-набора.

- **7.0 Platform Expansion**
  - устойчивый mesh/graph interoperability слой;
  - federation primitives и cross-domain policy enforcement;
  - масштабируемая observability/diagnostics модель для multi-node среды.

## 4. Архивные идеи

Исторические документы (старые execution plans и phase-драфты) вынесены в `docs/archive/`:

- [execution-plan.md](archive/execution-plan.md)
- [mesh-execution-plan.md](archive/mesh-execution-plan.md)
- [platform-execution-plan.md](archive/platform-execution-plan.md)
- [PHASE4_ROADMAP_V5.md](archive/PHASE4_ROADMAP_V5.md)
- [PHASE4_1_CIRCUIT_BREAKER_API_VALIDATION.md](archive/PHASE4_1_CIRCUIT_BREAKER_API_VALIDATION.md)
- [PHASE4_1_SMART_CIRCUIT_BREAKER_REVIEW.md](archive/PHASE4_1_SMART_CIRCUIT_BREAKER_REVIEW.md)
- [PHASE1_COMPLETE.md](archive/PHASE1_COMPLETE.md)

## 5. Долгосрочные цели

- Полностью transport-agnostic runtime с формальными SLA/QoS контрактами.
- Связанный стек Runtime ↔ Mesh ↔ Graph ↔ Platform без дублирующей логики.
- Предсказуемая эволюция 7.x через короткие инкременты с трассируемой документацией и тестами.
