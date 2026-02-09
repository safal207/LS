# WEB4PLATFORMEXECUTIONPLANGENERATOR.md — Autonomous Platform Milestone Executor

## 🎯 Назначение
Codex должен начать с чтения:

- `WEB4MESHEXECUTIONPLANGENERATOR.md`
- `mesh-execution-plan.md`
- `WEB4PLATFORMEXECUTIONPLANGENERATOR.md`

и затем выполнить все шаги из этого файла, действуя как полностью автономный архитектор и исполнитель Web4 Platform Milestone.

Этот документ определяет задание для Codex‑агента, который должен поднять Web4 на уровень платформы: завершить Mesh Runtime, построить Services Layer, Cloud API, Developer Portal, Billing и Marketplace (MVP).

---

## 🧠 Режим работы Codex

Codex должен работать как:

- Platform Architect — проектирует платформенную архитектуру.
- Mesh Engineer — завершает mesh‑runtime и интеграцию.
- Services Designer — строит service layer и stateful‑сервисы.
- Cloud Engineer — строит Cloud API и hosted nodes.
- Product Engineer — формирует developer portal и SDK‑примеры.
- Monetization Engineer — строит Billing Layer (MVP).
- Marketplace Builder — строит Marketplace (MVP).
- Planner — создаёт roadmap и под‑issues.
- Tester — пишет тесты.
- Documentarian — пишет документацию.

---

## 📦 Scope

Codex должен:

1. Прочитать milestone:
   - `WEB4MESHEXECUTIONPLANGENERATOR.md`
   - `mesh-execution-plan.md`
   - `WEB4PLATFORMEXECUTIONPLANGENERATOR.md`

2. Построить полный execution‑plan для платформы, включая:
   - завершение Mesh Runtime
   - Services Layer
   - Cloud API
   - Developer Portal
   - Billing Layer (MVP)
   - Marketplace (MVP)
   - тесты и CI/CD

3. Разбить milestone на под‑issues:
   - Mesh Runtime Completion
   - Services Layer
   - Distributed Memory
   - Event Pipelines
   - Service Registry
   - Cloud API
   - Hosted Nodes
   - Hosted Trust Verification
   - Hosted Observability
   - Developer Portal
   - Billing Layer
   - Marketplace
   - Platform Tests
   - Platform CI/CD

4. Создать структуру директорий:

```
python/modules/web4_platform/
    services.py
    service_registry.py
    distributed_memory.py
    event_pipeline.py
    cloud_api.py
    billing.py
    marketplace.py
    developer_portal.py
    __init__.py
```

5. Сгенерировать scaffolding кода:
   - Services Layer
   - distributed memory
   - event pipelines
   - service registry
   - cloud API stubs
   - billing counters
   - marketplace entities
   - portal scaffolding

6. Создать интеграционные тесты:
   - services over mesh
   - cloud API endpoints
   - billing counters
   - marketplace registry

7. Создать unit‑tests для всех модулей.

8. Создать CLI‑инструменты:
   - `scripts/web4platform_demo.py`
   - `scripts/web4platform_status.py`

9. Обновить CI/CD workflow:
   - добавить platform‑тесты
   - добавить platform‑линтинг
   - добавить platform‑type‑checking

10. Выполнить milestone полностью.

---

## 🧾 Одно командное задание для Codex

> Задание:
> Ты — автономный архитектор и исполнитель Web4 Platform Milestone.
> 1. Прочитай файлы:
>    - `WEB4MESHEXECUTIONPLANGENERATOR.md`
>    - `mesh-execution-plan.md`
>    - `WEB4PLATFORMEXECUTIONPLANGENERATOR.md`
> 2. На основе этих документов:
>    - Построй `platform-execution-plan.md` в корне репозитория.
>    - Разбей milestone на под‑issues (Mesh Runtime Completion, Services Layer, Distributed Memory, Event Pipelines, Service Registry, Cloud API, Hosted Nodes, Hosted Trust Verification, Hosted Observability, Developer Portal, Billing Layer, Marketplace, Platform Tests, Platform CI/CD).
>    - Создай структуру директорий и scaffolding кода.
>    - Реализуй минимально рабочие версии всех подсистем платформы.
>    - Добавь интеграционные тесты и unit‑тесты.
>    - Создай CLI‑инструменты.
>    - Обнови CI workflow.
> 3. Считай задачу выполненной только тогда, когда:
>    - все тесты проходят,
>    - Services работают поверх Mesh,
>    - Cloud API отвечает,
>    - Developer Portal собран,
>    - Billing считает usage,
>    - Marketplace отображает сущности,
>    - `platform-execution-plan.md` отражает фактически сделанное,
>    - результат оформлен в pull request.

---

## 🧪 Acceptance Criteria

Codex должен предоставить:

- `platform-execution-plan.md`
- список под‑issues
- структуру директорий
- scaffolding кода
- рабочий Services Layer
- рабочий Cloud API (MVP)
- Developer Portal (MVP)
- Billing Layer (MVP)
- Marketplace (MVP)
- полный набор тестов
- CLI‑инструменты
- обновлённый CI workflow

Все тесты должны проходить.

---

## 🚫 Out of Scope

- UI/GUI production‑quality
- PKI/HSM
- масштабирование > 100 узлов
- продвинутая оптимизация производительности

---

## 📊 Метрики успешности

- 100% тестов проходят
- Services Layer работает на mesh‑подсистемах
- Cloud API отвечает на базовые запросы
- Billing считает usage корректно
- Marketplace регистрирует сущности

---

## 🔗 Входные данные

Codex должен использовать:

- `WEB4MESHEXECUTIONPLANGENERATOR.md`
- `mesh-execution-plan.md`
- существующий Web4 Runtime + Mesh

---

## 🧩 Выходные данные

Codex должен сгенерировать:

- план
- код
- тесты
- документацию
- CI
- CLI

---

## 🧨 Режим выполнения

Codex должен:

- действовать автономно
- не ждать дополнительных указаний
- выполнить milestone полностью
- предоставить результат в виде pull request
