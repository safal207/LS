# LS — Local Cognitive System (LCS)

[![CI status](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Python tests](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)
[![Rust build](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml/badge.svg?branch=main)](https://github.com/safal207/LS/actions/workflows/web4_runtime_ci.yml)

LS (Local Cognitive System) — локальная когнитивная система: архитектурный слой поверх LLM, который добавляет агентный цикл, временной контекст, устойчивость и наблюдаемость.

Интервью‑копайлот (Ghost Mode) — **один из режимов/приложений**, а не “ядро” проекта.

Документация:
- `docs/MANIFESTO.md` — позиционирование и принципы
- `docs/ARCHITECTURE.md` — архитектура и поток данных
- `docs/CIP_SPEC.md` — Cognitive Interlink Protocol (агент‑агент)
- `docs/HCP_SPEC.md` — Human Connection Protocol (человек‑агент)
- `docs/LIP_SPEC.md` — Liminal Internet Protocol (обучение из интернета)
- `docs/WEB4_OVERVIEW.md` — обзор Web4
- `docs/WHITEPAPER_WEB4.md` — whitepaper Web4
- `docs/RFC_BUNDLE_WEB4.md` — единый RFC‑bundle
- `docs/RUST_TRANSPORT_SPEC.md` — спецификация Rust‑транспорта
- `docs/ARCH_DIAGRAMS.md` — архитектурные диаграммы (Mermaid)
- `docs/ROADMAP.md` — дорожная карта
- `schemas/*.schema.json` — формальные JSON Schema протоколов

## Структура репозитория

```
apps/
  console/   # CLI entrypoint
  ghostgpt/  # GUI entrypoint
python/
  modules/
    agent/          # AgentLoop + observability
    audio/          # аудио ingest
    stt/            # STT пайплайн
    llm/            # LLM пайплайн
    shared/         # shared utils + config loader
    hexagon_core/   # когнитивное ядро (beliefs/causal/mission/COT)
config/
  base.yaml
  console.yaml
  ghostgpt.yaml
  local.yaml (ignored)
```

## Что даёт LCS

- **AgentLoop**: состояния `idle/listening/thinking/responding`, cooperative cancellation, memory hooks, метрики.
- **Temporal/Belief foundation**: жизненный цикл убеждений и temporal‑индекс в `hexagon_core`.
- **Stability layer**: circuit breaker для LLM вызовов.
- **Observability**: event sink + строгий event‑contract (версия `1.0`).
- **Единый конфиг**: YAML `base → app → local` через `shared.config_loader`.

## Какая боль рынка мы закрываем

- **Недоверие к AI‑решениям в бизнесе**: нет прозрачного протокола для подтверждения фактов, источников и авторства решений.
- **Фрагментация агентных систем**: разные команды создают несвязанные агенты без общего trust‑ и state‑слоя.
- **Эскалация галлюцинаций**: ошибки распространяются между продуктами, потому что нет коллективной валидации знаний.
- **Отсутствие когнитивного контекста**: системы не знают о нагрузке, фокусе и намерении друг друга, из‑за чего UX деградирует.
- **Слабый слой согласия человека**: нет протокольного уровня для intent/consent/safety, который уважает человека.
- **Зависимость от централизованных платформ**: локальные команды теряют автономию и контроль над доверительной моделью.

## Быстрый старт

### 1) Установка зависимостей

```bash
python -m venv venv
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# CMD
venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Запуск

**Console (CLI):**
```bash
python apps/console/main.py
```

**GhostGPT (GUI):**
```bash
python apps/ghostgpt/main.py
```

### Legacy entrypoints (deprecated)

Эти entrypoints оставлены для обратной совместимости и будут удалены после стабилизации:
```bash
python main.py
python GhostGPT/main.py
```

## Конфигурация

Конфиги в YAML:
- `config/base.yaml` — общие параметры
- `config/console.yaml` — overrides для консоли
- `config/ghostgpt.yaml` — overrides для GUI
- `config/local.yaml` — локальные override (ignored)

Loader находится в `python/modules/shared/config_loader.py`:
```python
from shared.config_loader import load_config
cfg = load_config("console")
```

Также работает совместимый импорт:
```python
from modules.shared.config_loader import load_config
```

Для локальных настроек используйте шаблон:
```
config/local.example.yaml
```
Скопируйте его в `config/local.yaml` и внесите свои значения (ключи, модели и т.п.).

## Режимы (в т.ч. Interview Mode)

Поведение системы в первую очередь задаётся `llm.system_prompt` (см. `config/base.yaml` и overrides в `config/local.yaml`).

Если нужен “интервью‑режим”, задайте системный промпт в `config/local.yaml` (пример):
```yaml
llm:
  system_prompt: |
    You are a senior developer interviewing candidates.
    Provide concise, bullet-point answers suitable for technical interviews.
    Answer in Russian.
```

## Модули

Единый модульный слой находится в `python/modules/`:
- `agent/` — AgentLoop и observability
- `audio/` — ingest/VAD
- `stt/` — Whisper обработка
- `llm/` — генерация ответов (Ollama/Groq/Qwen)
- `shared/` — общие утилиты и конфиг
- `hexagon_core/` — когнитивное ядро агента

## Совместимость

Для поддержки старых импортов оставлены stubs на корне:
`audio_module.py`, `stt_module.py`, `llm_module.py`, `qwen_handler.py`, `utils.py`.

## Smoke‑тесты

```bash
python apps/console/main.py
python apps/ghostgpt/main.py
python -c "from modules.shared.config_loader import load_config; print(load_config('console'))"
python scripts/smoke.py
```

## Примечания

- Все вычисления — локально (кроме опционального cloud‑fallback, если включён).
- Для системного аудио на Windows обычно нужен VB‑Cable или включенный Stereo Mix (зависит от железа/драйверов).
