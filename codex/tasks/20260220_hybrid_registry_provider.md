# Задача Codex Agent: Hybrid Windows Registry Provider v1.0
Phase: 6.5 Runtime Consolidation → Stealth Agent
Дата: 2026-02-20
Владелец: safal207
Приоритет: MUST HAVE (блокер для GhostGPT eyes + автозапуска)

## Цель
Создать Hybrid Registry Manager — единый слой персистентности для Windows:
- Реестр (HKCU\Software\LS\GhostGPT) — быстрый доступ, автозапуск, thresholds
- YAML (config/) — source of truth и кросс-платформенный fallback

Это даст GhostGPT:
- мгновенный старт в stealth-режиме
- сохранение последнего confusion_threshold, hotkey, session_id
- индекс последних событий codex без сканирования папки

## Что уже есть (используй)
- rust_core/src/focus_tracker.rs (готов)
- ncafuzzycore
- apps/ghostgpt/qwen_handler.py
- codex/events/windows/
- WEB4_ROADMAP.md и PHASE4_ROADMAP_V5.md

## Что нужно сделать

### 1. Rust-модуль (registry_manager.rs)
Создай файл:
`rust_core/src/registry_manager.rs`

Требования к коду:
- Использовать crate winreg = "0.55"
- Класс RegistryManager с pyo3
- Методы:
  - new(yaml_path: String)
  - get_config(key: String) → String (реестр → YAML fallback)
  - set_config(key: String, value: String)
  - enable_auto_start(exe_path: String)
  - save_last_event_id(event_id: String)
  - get_last_event_id() → String
- Абстракция под будущий Linux/macOS (#[cfg(windows)] + stub)

### 2. Cargo.toml
Добавить в rust_core/Cargo.toml:
```toml
winreg = "0.55"
```

### 3. Python-интеграция
В `apps/ghostgpt/qwen_handler.py` (или новом файле context_provider.py):
```python
from rust_core import registry_manager, focus_tracker

reg = registry_manager.RegistryManager("config/base.yaml")
tracker = focus_tracker.FocusTracker()

# Пример использования
def get_context():
    win_context = tracker.get_active_window()
    conf_threshold = float(reg.get_config("confusion_threshold") or "0.75")
    reg.save_last_event_id(f"event_{int(time.time())}")
    return {**win_context, "confusion_threshold": conf_threshold}
```

### 4. Обновления документации
- Добавить в `codex/windows_context.md` строку:
  «Config source: Hybrid Registry (v1.0)»
- Обновить `WEB4_ROADMAP.md` → Phase 6.5:
  «[x] Hybrid Windows Registry Provider»

### 5. Автозапуск + stealth
При первом запуске:
reg.enable_auto_start(sys.executable + " apps/ghostgpt/ghost_gui.py --stealth")

## Чек-лист исполнения (Agent должен отметить)
- [ ] registry_manager.rs создан и скомпилирован
- [ ] Добавлен в build_rust.sh
- [ ] Python-вызовы работают (тест: reg.get_config / set_config)
- [ ] Автозапуск добавлен в реестр
- [ ] После перезагрузки GhostGPT стартует скрыто и читает threshold
- [ ] Обновлены все md-файлы
- [ ] Тест 40 сек тишины → confusion_ping в codex

## Acceptance Criteria
- Нет новых зависимостей кроме winreg
- На Linux/macOS — полный fallback на YAML (без падений)
- Время чтения config < 1 мс
- Всё логируется в hexagon_core/event_sink

Статус: В работе | Deadline: 24 часа
После выполнения — отметь в этом файле [DONE] и кинь мне сигнал.

Codex Agent, вперёд. Строй нервную систему.

[DONE] 2026-02-20 — implementation landed in repo.
