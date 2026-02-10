# Отчёт: текущее состояние главной ветки

Дата анализа: 2026-02-10

## Краткий summary

1. В локальном репозитории отсутствует отдельная ветка `main`; доступна только ветка `work`, поэтому фактический анализ выполнен по текущему HEAD (предположительно актуальному состоянию проекта).  
2. CI-инфраструктура присутствует в двух workflow: целевой `web4_runtime_ci.yml` (ruff + mypy + pytest + cargo build) и `ruff_autofix.yml` (автофикс Python-кода в PR).  
3. Локальная прогонка шагов из CI для Web4-модулей зелёная: `ruff`, `mypy`, `pytest` и `cargo build` проходят, но Rust-сборка выдаёт предупреждения PyO3 и одно `dead_code`-предупреждение.  
4. Rust-часть (`rust_core/`) собирается и тестируется без падений, но не содержит unit/integration тестов (0 тестов), что создаёт пробел в регрессионном контроле.  
5. В Rust-ядре отсутствуют отдельные модули `CTE/CAPU/belief/mission` — эти доменные части реализованы в Python (`python/modules/hexagon_core/*`), а Rust реализует инфраструктурные классы (`MemoryManager`, `PatternMatcher`, `Storage`, `Transport*`, `Web4RttBinding`).  
6. Python-часть структурно богата и покрыта большим количеством тестов; при этом есть места с fallback/заглушечным поведением (silent fallback в `rust_bridge.py`, несколько `pass`/минимальных реализаций), которые стоит формализовать как технический долг.  

---

## 1) Состояние инфраструктуры

### 1.1 CI workflows

Найдены workflow:
- `.github/workflows/web4_runtime_ci.yml`
- `.github/workflows/ruff_autofix.yml`

Что делает `web4_runtime_ci.yml`:
- запускается на `push`/`pull_request` по путям Web4 + `rust_core/**`;
- устанавливает Python 3.11 и инструменты (`pytest`, `ruff`, `mypy`, `requests`, `PyYAML`);
- выполняет `ruff check` по Web4-модулям и связанным скриптам;
- выполняет `mypy` по пакетам `python.modules.web4_*`;
- выполняет `pytest` по 4 web4-тестам;
- выполняет `cargo build` в `rust_core`.

### 1.2 Наличие и корректность autofix workflow

`ruff_autofix.yml` присутствует и в целом корректен:
- триггер только на `pull_request` по `python/**`;
- есть `permissions: contents: write`;
- исключён цикл автокоммитов (`if: github.actor != 'github-actions[bot]'`);
- автофиксит `ruff check python --fix --unsafe-fixes`;
- коммитит и пушит изменения только если есть diff.

Потенциальный риск: `--unsafe-fixes` может вносить semantically-risky изменения без дополнительного review gate.

### 1.3 Линтеры и типизация (ruff/mypy)

Локальная прогонка команд из CI:
- `ruff check ...` → `All checks passed!`
- `mypy ...` → `Success: no issues found in 28 source files`

### 1.4 Тесты (pytest)

Локальная прогонка CI-набора тестов Web4:
- `python/tests/test_web4_runtime.py`
- `python/tests/test_web4_mesh.py`
- `python/tests/test_web4_graph.py`
- `python/tests/test_web4_bio.py`

Результат: `21 passed`.

### 1.5 Ошибки/предупреждения/нестабильности

- CI-статус GitHub (green/red badges, flaky history) локально недоступен без remote metadata/API.
- `cargo build` и `cargo test` дают повторяющиеся предупреждения PyO3 (`non-local impl definition`) и одно `dead_code`-предупреждение по `max_size_mb`.
- Ограниченный scope CI: текущий workflow покрывает только Web4-подмножество и `cargo build`, но не запускает полный Python test-suite и не делает `cargo test`.

---

## 2) Состояние Rust-части (`rust_core/`)

### 2.1 Cargo.toml и Cargo.lock

- `Cargo.toml` валиден, содержит актуально выглядящие зависимости: `pyo3`, `tokio`, `rayon`, `sled`, `serde`, `rand` и др.
- `Cargo.lock` присутствует (lockfile зафиксирован).
- Сборка успешна (`cargo build`).

### 2.2 Консистентность зависимостей

- Явных конфликтов зависимостей не выявлено (проект собрался).
- Наблюдаются предупреждения, указывающие на потенциально устаревшую связку `pyo3`/`pyo3_macros` относительно текущих warning-правил компилятора.

### 2.3 PyO3-интеграция

PyO3-интеграция функциональна:
- `lib.rs` экспортирует Python-модуль `ghostgpt_core`;
- в модуль добавляются классы `MemoryManager`, `PatternMatcher`, `Storage`, `TransportConfig`, `TransportHandle`, `Web4RttBinding`;
- Python-обвязка (`python/rust_bridge.py`) использует эти классы с graceful fallback, если расширение недоступно.

### 2.4 Состояние модулей (`ghostgpt_core`, CTE, CAPU, belief, mission)

- `ghostgpt_core`: есть, собирается, предоставляет инфраструктурное ядро.
- `CTE`, `CAPU`, `belief`, `mission` в Rust-части **не обнаружены** как отдельные модули.
- Эти доменные блоки обнаружены в Python (`python/modules/hexagon_core/cte.py`, `capu.py`, `belief/*`, `mission/*`).

### 2.5 Незавершённые/пустые модули

- Полностью пустых `.rs` модулей не найдено.
- Есть технические признаки незавершённости качества: отсутствие Rust-тестов и warning-уровень PyO3 интеграции.

### 2.6 Rust-тесты

- `cargo test` проходит.
- Фактически выполнено `0 tests` (и для lib, и для `kacl_aggregator`), то есть поведение Rust-кода не покрыто автотестами.

---

## 3) Состояние Python-части (`python/`)

### 3.1 Структура модулей

Структура широкая и модульная: `agent`, `coordinator`, `field`, `orientation`, `llm`, `web4_runtime`, `web4_mesh`, `web4_graph`, `web4_bio`, `hexagon_core` и др. Есть отдельные `python/tests/*`.

### 3.2 Состояние Python-обвязки над Rust

`python/rust_bridge.py` реализует robust-wrapper:
- модульный import `ghostgpt_core` с fallback;
- при недоступности Rust работает в `available=False` режиме;
- большинство операций обёрнуты в безопасные методы, возвращающие дефолты на ошибках.

Это улучшает отказоустойчивость, но может маскировать деградацию производительности/функциональности, если Rust-часть не загрузилась.

### 3.3 Наличие/отсутствие заглушек

Найдены индикаторы заглушечного/минимального поведения:
- несколько `pass` в runtime-коде и тестах;
- fallback-логика в мосте Rust↔Python, которая скрывает часть исключений.

Полноценных блокирующих `NotImplementedError` в критических путях Web4-части не выявлено.

### 3.4 Состояние тестов

- Целевой CI-набор Web4 тестов: 21/21 passed.
- В репозитории есть значительно более широкий набор тестов (`tests/unit`, `tests/smoke`, `tests/e2e` и `python/tests/*`), но они не входят в текущий CI workflow и не оценивались целиком в рамках этого прогона.

### 3.5 Соответствие API между Python и Rust

- На уровне интерфейсов `rust_bridge.py` согласован с экспортируемыми Rust-классами (`MemoryManager`, `PatternMatcher`, `Storage`, `Transport*`, `Web4RttBinding`).
- Возможный functional gap: часть методов в Python зависит от опциональности и runtime-наличия Rust-модуля; при отсутствии расширения поведение переводится в fallback без hard-fail.

---

## 4) Общая картина проекта

### Что завершено

- Базовый Web4 CI pipeline настроен и локально воспроизводим.
- Ключевые Web4 Python-модули проходят lint/type/tests.
- Rust core собирается и интегрирован с Python через PyO3.

### Что в процессе

- Укрепление качества Rust-компонента (предупреждения компилятора + отсутствие тестов).
- Расширение покрытия CI за пределы Web4-подмножества.
- Нормализация поведения fallback-сценариев Rust bridge.

### Что требует внимания

- Нет локально доступного `main`-рефа: требуется синхронизация веточной политики/remote tracking.
- Нет Rust unit/integration тестов.
- В CI нет полного набора тестов репозитория.
- Есть warning-след от PyO3 макросов.

### Риски/технические долги

1. Ложное ощущение стабильности: CI зелёный только на ограниченном наборе путей/тестов.  
2. Тихая деградация при недоступном Rust backend из-за fallback-поведения.  
3. Отсутствие Rust-тестов затрудняет безопасный рефакторинг transport/runtime-логики.  
4. `unsafe` autofix в PR может вносить неожиданные правки.  

### Логичные следующие шаги

1. Добавить в CI отдельные джобы `cargo test` и `cargo clippy -- -D warnings` (или согласованный warning-policy).  
2. Добавить минимальный Rust unit-test coverage для `memory_manager`, `pattern_matcher`, `transport`.  
3. Расширить Python CI до smoke/unit-контуров (поэтапно, чтобы не взорвать время прогона).  
4. Для `ruff_autofix` рассмотреть отказ от `--unsafe-fixes` либо добавить label/approval-gate.  
5. В `rust_bridge.py` добавить более явную телеметрию режима fallback (метрики/health signal), чтобы деградация была наблюдаемой.  
6. Синхронизировать веточную модель: восстановить/подтвердить `main` как отслеживаемую ветку и привязать анализ к точному commit SHA основной ветки.

---

## Команды, выполненные при анализе

```bash
rg --files .github/workflows
sed -n '1,260p' .github/workflows/web4_runtime_ci.yml
sed -n '1,260p' .github/workflows/ruff_autofix.yml
python -m pip install --upgrade pip
python -m pip install pytest ruff mypy requests PyYAML
ruff check python/modules/web4_runtime python/modules/web4_mesh python/modules/web4_graph python/modules/web4_bio scripts/web4_demo.py scripts/web4_mesh_demo.py scripts/web4meshdemo.py scripts/web4meshinspect.py scripts/web4meshtopology.py python/tests/test_web4_runtime.py python/tests/test_web4_mesh.py python/tests/test_web4_graph.py python/tests/test_web4_bio.py
MYPYPATH=python mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports -p python.modules.web4_runtime -p python.modules.web4_mesh -p python.modules.web4_graph -p python.modules.web4_bio
PYTHONPATH=. pytest python/tests/test_web4_runtime.py python/tests/test_web4_mesh.py python/tests/test_web4_graph.py python/tests/test_web4_bio.py
cd rust_core && cargo build
cd rust_core && cargo test
```
