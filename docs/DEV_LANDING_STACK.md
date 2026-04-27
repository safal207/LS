# Локальный стек: лендинг + Reflection API + HCP API

Один сценарий для **`ghostgpt-ls-landing`**: панели **Runtime Live** (reflection) и **HCP Marketplace** ходят на два HTTP-сервиса в репозитории.

## Порты и переменные

| Сервис | Порт по умолчанию | Назначение |
|--------|-------------------|------------|
| Reflection Dashboard API | **8780** | `GET /api/reflection/snapshot`, `POST /api/reflection/action` |
| HCP Marketplace API | **8781** | `GET /api/hcp/items`, `POST` purchase/install/load |

В Vite (лендинг):

| Переменная | Значение по умолчанию в `.env.example` |
|------------|----------------------------------------|
| `VITE_REFLECTION_API_BASE` | `http://127.0.0.1:8780` |
| `VITE_HCP_API_BASE` | `http://127.0.0.1:8781` |

Скопируйте `ghostgpt-ls-landing/.env.example` → `ghostgpt-ls-landing/.env` и при необходимости поменяйте хост/порты. Перезапустите `npm run dev` после правок.

## Быстрый старт (Windows)

Из корня репозитория:

```powershell
.\scripts\dev_landing_stack.ps1
```

Вариант **одно окно, один процесс Python** (Reflection + HCP вместе):

```powershell
.\scripts\dev_landing_stack.ps1 -SingleProcess
```

Либо напрямую:

```powershell
$env:PYTHONPATH = "$pwd;$pwd\python"
python scripts/run_dev_stack_api.py
# с PluginManager для HCP:
python scripts/run_dev_stack_api.py --bootstrap apps/console/main.py
```

Скрипт `dev_landing_stack.ps1` при отсутствии файла создаст `ghostgpt-ls-landing/.env` из `.env.example`. Два окна по умолчанию; с `-SingleProcess` — одно. Затем в **отдельном** терминале:

```powershell
cd ghostgpt-ls-landing
npm install
npm run dev
```

Лендинг: обычно `http://127.0.0.1:5173` (см. вывод Vite).

### HCP с PluginManager (кнопка «Load» на панели)

```powershell
.\scripts\dev_landing_stack.ps1 -HcpWithBootstrap
# или одно окно:
.\scripts\dev_landing_stack.ps1 -SingleProcess -HcpWithBootstrap
```

## Вручную (любая ОС)

**Терминал 1 — Reflection**

```bash
# из корня репозитория
export PYTHONPATH=.
python scripts/run_reflection_dashboard_api.py --port 8780
```

**Терминал 2 — HCP**

```bash
export PYTHONPATH=.:python
python scripts/run_hcp_marketplace_api.py --port 8781
```

**Терминал 3 — Vite** — команды как выше.

## CORS

- Reflection: `REFLECTION_CORS_ORIGIN` (по умолчанию `*`).
- HCP: `HCP_CORS_ORIGIN` (по умолчанию `*`).

Для жёсткого origin, например Vite: `http://127.0.0.1:5173`, задайте эти переменные **перед** запуском Python-процессов.

## Проверка

```text
curl -s http://127.0.0.1:8780/api/reflection/snapshot?recent_limit=1 | head
curl -s http://127.0.0.1:8781/api/hcp/health
```

## См. также

- `docs/HCP_MARKETPLACE_MVP.md` — HCP API.
- `agent/reflection_dashboard_api.py` — контракт reflection (через скрипт-обёртку `scripts/run_reflection_dashboard_api.py`).
