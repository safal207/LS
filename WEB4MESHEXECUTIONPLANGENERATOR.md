# WEB4MESHEXECUTIONPLANGENERATOR.md — Autonomous Mesh Milestone Executor (Next Level)

## 🎯 Назначение
Codex должен начать с чтения:

- `docs/CIPRUNTIMEINTEGRATION_ISSUE.md`
- `WEB4MESHEXECUTIONPLANGENERATOR.md`

и затем выполнить все шаги из этого файла, действуя как полностью автономный архитектор и исполнитель Web4 Mesh Milestone.

Этот документ определяет задание для Codex‑агента, который должен построить распределённый Web4 Mesh Runtime, расширяющий текущий Web4 Runtime до многосетевого режима.

---

## 🧠 Режим работы Codex

Codex должен работать как:

- Mesh Architect — проектирует распределённую архитектуру.
- Network Engineer — создаёт mesh‑routing и peer‑protocols.
- Trust Systems Designer — расширяет TrustFSM до сетевого уровня.
- Planner — создаёт roadmap и под‑issues.
- Implementer — пишет код.
- Integrator — связывает mesh с существующим runtime.
- Tester — создаёт тесты для многосетевого режима.
- Documentarian — пишет документацию.

Codex должен выполнять milestone полностью автономно, без ожидания дополнительных указаний.

---

## 📦 Scope

Codex должен:

1. Прочитать milestone:
   - `docs/CIPRUNTIMEINTEGRATION_ISSUE.md`
   - `WEB4MESHEXECUTIONPLANGENERATOR.md`

2. Построить полный execution‑plan для Mesh, включая:
   - архитектуру mesh‑routing
   - multi‑peer handshake
   - trust propagation
   - deferred acceptance across peers
   - mesh‑observability
   - mesh‑RTT
   - CLI‑mesh инструменты
   - тесты
   - CI

3. Разбить milestone на под‑issues:
   - MeshRouter
   - PeerRegistry
   - MeshEnvelope
   - MeshForwardingPolicy
   - CIP Mesh Handshake
   - Distributed TrustFSM
   - Mesh RTT
   - Mesh Observability
   - Mesh CLI Tools
   - Mesh Tests
   - Integration with Web4 Runtime

4. Создать структуру директорий:

```
python/modules/web4_mesh/
    router.py
    peers.py
    trust_mesh.py
    observability_mesh.py
    mesh_rtt.py
    __init__.py
```

5. Сгенерировать scaffolding кода:
   - MeshRouter
   - PeerRegistry
   - MeshEnvelope
   - forwarding logic
   - multi‑hop routing
   - trust propagation
   - mesh RTT
   - observability

6. Создать интеграционные тесты:
   - multi‑peer handshake
   - routing correctness
   - trust propagation
   - deferred acceptance across peers
   - mesh RTT reconnect/backpressure
   - mesh observability

7. Создать unit‑tests для всех модулей.

8. Создать CLI‑mesh инструменты:
   - `scripts/web4meshinspect.py`
   - `scripts/web4meshtopology.py`
   - обновлённый `scripts/web4meshdemo.py`

9. Обновить CI/CD workflow:
   - добавить mesh‑тесты
   - добавить mesh‑линтинг
   - добавить mesh‑type‑checking

10. Выполнить milestone полностью.

---

## 🧾 Одно командное задание для Codex

> Задание:
> Ты — автономный архитектор и исполнитель Web4 Mesh Milestone.
> 1. Прочитай файлы:
>    - `docs/CIPRUNTIMEINTEGRATION_ISSUE.md`
>    - `WEB4MESHEXECUTIONPLANGENERATOR.md`
> 2. На основе этих документов:
>    - Построй `mesh-execution-plan.md` в корне репозитория.
>    - Разбей milestone на под‑issues (MeshRouter, PeerRegistry, MeshEnvelope, MeshForwardingPolicy, CIP Mesh, Distributed TrustFSM, Mesh RTT, Mesh Observability, Mesh CLI Tools, Mesh Tests).
>    - Создай структуру директорий и scaffolding кода.
>    - Реализуй минимально рабочие версии всех mesh‑подсистем.
>    - Добавь интеграционные тесты и unit‑тесты.
>    - Создай CLI‑mesh инструменты.
>    - Обнови CI workflow.
> 3. Считай задачу выполненной только тогда, когда:
>    - все тесты проходят,
>    - mesh‑демо работает без ошибок,
>    - `mesh-execution-plan.md` отражает фактически сделанное,
>    - результат оформлен в pull request.

---

## 🧪 Acceptance Criteria

Codex должен предоставить:

- `mesh-execution-plan.md`
- список под‑issues
- структуру директорий
- scaffolding кода
- рабочий MeshRouter
- рабочий PeerRegistry
- рабочий multi‑peer handshake
- distributed TrustFSM
- mesh RTT
- mesh observability
- полный набор тестов
- CLI‑mesh инструменты
- обновлённый CI workflow

Все тесты должны проходить.

---

## 🚫 Out of Scope

- UI/GUI
- PKI/HSM
- mesh > 50 узлов
- продвинутая оптимизация маршрутизации

---

## 📊 Метрики успешности

- 100% тестов проходят
- multi‑peer handshake стабилен
- routing корректен на 3 узлах
- trust propagation работает
- mesh‑observability показывает топологию
- CLI‑mesh работает

---

## 🔗 Входные данные

Codex должен использовать:

- `docs/CIPRUNTIMEINTEGRATION_ISSUE.md`
- спецификации CIP/HCP/LIP
- существующий Web4 Runtime

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

---

Если хочешь, я могу:

- оформить это в виде PR‑готового файла,
- подготовить версию для GitHub Issue,
- или сразу сформировать команду, которую ты дашь Codex.

Как двигаемся дальше, Alex.
