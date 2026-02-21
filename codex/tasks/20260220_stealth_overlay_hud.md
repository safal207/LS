# Задача Codex Agent: Stealth Overlay HUD v1.0
Phase: 6.5 Runtime Hardening+ → Stealth Agent
Дата: 2026-02-20
Владелец: safal207
Приоритет: MUST HAVE (визуализация confusion_ping)

## Цель
Создать неинвазивный HUD-оверлей (1px glow-полоска по краю экрана), который:
- появляется только при confusion_ping > threshold
- исчезает через 3 секунды или при любом вводе
- управляется горячей клавишей Alt + G (toggle stealth)
- полностью интегрируется с существующим AgentLoop + collect_windows_context

Это даст GhostGPT «тело» — ты будешь физически видеть, когда система тебя «чувствует».

## Что уже есть (используй)
- apps/ghostgpt/qwen_handler.py + init_stealth()
- python/modules/agent/loop.py (_maybe_collect_windows_context + liminal_transition)
- rust_core (RegistryManager + FocusTracker stub)
- PyQt6 уже в зависимостях проекта
- codex/events/windows/ + index.json

## Что нужно сделать

### 1. Новый модуль (apps/ghostgpt/overlay.py)
Создай файл:
`apps/ghostgpt/overlay.py`

Требования:
- Использовать PyQt6 (QWidget, translucent, frameless, always-on-top)
- Режимы: 1px glow по нижнему краю (цвет #00ff88 с blur)
- Hotkey: Alt + G (глобальный, через QHotkey или keyboard)
- Слушать событие "liminal_transition" из AgentLoop
- Автоскрытие через 3 секунды
- Полная совместимость с --stealth флагом

### 2. Интеграция в init_stealth()
В `apps/ghostgpt/qwen_handler.py` добавить:
```python
from .overlay import StealthOverlay

def init_stealth():
    reg = get_registry_manager()
    overlay = StealthOverlay()
    overlay.show()  # сразу в фоне, прозрачный
    # подписка на события из loop
    return reg, overlay
```

### 3. Подключение к AgentLoop
В `python/modules/agent/loop.py` в `_emit` добавить:
```python
if event_type == "liminal_transition":
    self.event_sink.emit("overlay_trigger", payload)  # overlay слушает
```

### 4. Обновления документации
- Добавить в `codex/windows_context.md`: «+ Stealth Overlay HUD v1.0»
- Обновить `WEB4_ROADMAP.md` в 6.5:
  ```markdown
  - [x] Hybrid Windows Registry Provider
  - [ ] Stealth Overlay HUD v1.0 (1px glow + Alt+G)
  ```

### 5. Чек-лист исполнения
- [ ] overlay.py создан и работает (тест: Alt+G → glow появляется/исчезает)
- [ ] Интеграция с AgentLoop (40 сек тишины → glow на 3 сек)
- [ ] Работает вместе с --stealth
- [ ] Нет мерцания, CPU < 1 % в idle
- [ ] Добавлен в build / packaging
- [ ] Обновлены все md-файлы

## Acceptance Criteria
- Оверлей полностью прозрачный в обычном режиме
- Glow появляется только по confusion_ping
- Hotkey работает глобально
- Не ломает основной AgentLoop
- Zero new heavy deps (только PyQt6, который уже есть)

Статус: В работе | Deadline: 12 часов
После выполнения — отметь **[DONE]** и кинь мне сигнал.

Codex Agent, вперёд. Делаем GhostGPT видимым, но невидимым одновременно.
