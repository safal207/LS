# Задача Codex Agent: Causal Temporal Memory в Registry v1.0
Phase: 6.5 Runtime Hardening+ → 7.0 Platform Expansion (Temporal Graph foundation)
Дата: 2026-02-20
Владелец: safal207
Приоритет: MUST HAVE (основа самоулучшения и Web4-федерации)

## Цель
Создать в HKCU\Software\LS\GhostGPT\CausalMemory постоянную причинно-следственную память:
- Каждое «причина → решение» сохраняется в реестре (REG_MULTI_SZ) + дублируется в codex/causal_memory/
- Быстрый доступ <1 мс (реестр) + полная история в JSON
- Автоматическое сохранение после успешного ответа LLM
- Чтение последних N записей для промптинга (RAG-style)

Это даст GhostGPT настоящую «память опыта»: он будет помнить не только факты, а **почему** проблема возникла и **как** её решили.

## Что уже есть (используй)
- rust_core/src/registry_manager.rs (Hybrid Registry v1.0)
- python/modules/llm/qwen_handler.py + collect_windows_context
- python/modules/agent/loop.py (_maybe_collect_windows_context + _emit)
- codex/events/windows/ + schema
- WEB4_ROADMAP.md

## Что нужно сделать

### 1. Расширение registry_manager.rs
Добавь в существующий файл `rust_core/src/registry_manager.rs` (в конец impl RegistryManager):

```rust
#[pymethods]
impl RegistryManager {
    fn save_cause_solution(&self, cause: String, solution: String, confidence: f32) -> PyResult<()> {
        let entry = format!(
            r#"{{"ts":"{}","cause":"{}","solution":"{}","confidence":{}}}"#,
            chrono::Utc::now().to_rfc3339(),
            cause.replace('"', r#"\""#),
            solution.replace('"', r#"\""#),
            confidence
        );

        #[cfg(windows)]
        {
            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            let (key, _) = hkcu.create_subkey_with_flags(
                r"Software\LS\GhostGPT\CausalMemory",
                KEY_ALL_ACCESS | KEY_WOW64_64KEY,
            )?;

            let mut entries: Vec<String> = key.get_value("entries").unwrap_or_default();
            entries.insert(0, entry);
            if entries.len() > 50 { entries.truncate(50); }
            key.set_value("entries", &entries)?;
            key.set_value("last_timestamp", &chrono::Utc::now().to_rfc3339())?;
            Ok(())
        }

        #[cfg(not(windows))]
        {
            let path = self.yaml_fallback.with_file_name("causal_memory.yaml");
            let mut content = if path.exists() { fs::read_to_string(&path)? } else { String::new() };
            content.push_str(&format!("- {}\n", entry));
            fs::write(path, content)?;
            Ok(())
        }
    }

    fn get_recent_causes(&self, limit: u32) -> PyResult<Vec<PyObject>> {
        // ... (реализация чтения и парсинга в PyDict — как в предыдущем примере)
    }
}
```

**Добавить в Cargo.toml** (если chrono ещё нет):
```toml
[target.'cfg(windows)'.dependencies]
chrono = { version = "0.4", features = ["serde"] }
```

### 2. Python-интеграция
В `python/modules/llm/qwen_handler.py` добавить:

```python
def save_cause_solution(cause: str, solution: str, confidence: float = 0.85):
    reg = get_registry_manager()
    if reg:
        reg.save_cause_solution(cause, solution, confidence)
        save_to_codex({  # дублируем в codex
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "causal_memory",
            "cause": cause,
            "solution": solution,
            "confidence": confidence,
            "source": "registry::causal_memory"
        })
```

В `AgentLoop` после успешного `_process` (в `_process_item`):
```python
if result is not None:
    save_cause_solution(
        cause=question,
        solution=result,
        confidence=0.9
    )
```

### 3. Новая папка в codex
Создай `codex/causal_memory/` + `.gitkeep` + `index.json` (аналогично windows/)

### 4. Обновления документации
- Добавить в `codex/windows_context.md`: «+ Causal Temporal Memory (Registry + codex)»
- В `WEB4_ROADMAP.md` (6.5):
  ```markdown
  - [x] Hybrid Windows Registry Provider
  - [x] Stealth Overlay HUD v1.0
  - [ ] Causal Temporal Memory v1.0 (причины + решения во времени)
  ```

### 5. Чек-лист исполнения
- [ ] registry_manager.rs расширен + скомпилирован
- [ ] save_cause_solution вызывается после успешного ответа LLM
- [ ] В regedit видно ветку CausalMemory с 50 записями
- [ ] get_recent_causes работает в Python
- [ ] После перезагрузки память сохраняется
- [ ] Обновлены все md-файлы

## Acceptance Criteria
- Запись < 2 мс, чтение < 1 мс
- Максимум 50 записей в реестре (rolling)
- Полная совместимость Linux/macOS (YAML)
- Логирование в hexagon_core/event_sink
- Готово к RAG-промптингу в qwen_handler

Статус: В работе | Deadline: 12 часов
После выполнения — отметь **[DONE]** и кинь мне сигнал.

Codex Agent, вперёд. Строим настоящую память машины.
