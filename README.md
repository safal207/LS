# Local Interview Copilot (Ghost Mode)

Десктопное приложение для помощи в онлайн‑собеседованиях: захватывает системный звук, транскрибирует речь интервьюера и показывает подсказки в реальном времени.

## Структура репозитория

```
apps/
  console/   # CLI entrypoint
  ghostgpt/  # GUI entrypoint
python/
  modules/
    audio/          # аудио ingest
    stt/            # STT пайплайн
    llm/            # LLM пайплайн
    shared/         # shared utils + config loader
    hexagon_core/   # ядро агента
config/
  base.yaml
  console.yaml
  ghostgpt.yaml
  local.yaml (ignored)
```

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

Конфиги теперь в YAML:
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

## Модули

Единый модульный слой находится в `python/modules/`:
- `audio/` — ingest/VAD
- `stt/` — Whisper обработка
- `llm/` — генерация ответов (Ollama/Groq/Qwen)
- `shared/` — общие утилиты и конфиг
- `hexagon_core/` — ядро агента

## Совместимость

Для поддержки старых импортов оставлены stubs на корне:
`audio_module.py`, `stt_module.py`, `llm_module.py`, `qwen_handler.py`, `utils.py`.

## Smoke‑тесты

```bash
python apps/console/main.py
python apps/ghostgpt/main.py
python -c "from modules.shared.config_loader import load_config; print(load_config('console'))"
```

## Примечания

- Все вычисления — локально (кроме опционального Groq‑fallback).
- Для системного аудио на Windows обычно нужен VB‑Cable.
