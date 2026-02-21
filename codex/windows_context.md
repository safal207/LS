# Windows Context Provider v1.0
Phase: 6.5 Runtime Consolidation → Stealth Agent

## Требования
1. Rust-модуль `focus_tracker` уже готов (см. предыдущий код).
2. Каждый вызов `tracker.get_active_window()` → сразу сохраняется в codex.
3. При confusion_score > 0.7 → генерируется событие "confusion_ping".
4. Максимум 10 событий в памяти (остальное — в JSON-файлах).

## Интеграция в Python (добавь в apps/ghostgpt/qwen_handler.py)

```python
from rust_core import focus_tracker
import json
from pathlib import Path

tracker = focus_tracker.FocusTracker()
codex_path = Path("codex/events/windows")

def save_to_codex(event_data):
    ts = event_data["timestamp"].replace(":", "").replace("-", "")
    file = codex_path / f"focus_event_{ts}.json"
    file.write_text(json.dumps(event_data, ensure_ascii=False, indent=2))
```

## Следующие шаги (чек-лист)
- [ ] Добавить в AgentLoop вызов `tracker.get_active_window()` каждые 5 сек + при фокусе
- [ ] Подключить fuzzy_confusion_score к ncafuzzycore
- [ ] Обновить PHASE4_ROADMAP_V5.md → добавить пункт "Windows Context Provider"
- [ ] Тест: 40 секунд сидишь в VS Code → GhostGPT должен мягко подсветить overlay

**Статус:** В работе | Приоритет: MUST HAVE | Владелец: safal207

Config source: Hybrid Registry (v1.0)
+ Causal Temporal Memory v1.2 + LCE + LTP
