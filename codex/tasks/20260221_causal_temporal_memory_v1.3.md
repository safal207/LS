# Задача Codex Agent: Causal Temporal Memory + LCE + LTP + LRI Integration v1.3
Phase: 6.5 Runtime Hardening+ → 7.0 Platform Expansion (Temporal Graph + Living Identity)
Дата: 2026-02-21
Владелец: safal207
Приоритет: MUST HAVE

## Цель
Создать в HKCU\Software\LS\GhostGPT\CausalMemory постоянную память, где каждое «причина → решение» хранится:
- вместе с полным LCE (docs/LCE_IN_LS.md)
- вместе с LTP trace (L-THREAD repo)
- вместе с LRI-Core (Living Relational Identity invariants, emotional-drift, resonance map, stabilizer)

Это превращает память в **живую, не-редуктивную, verifiable нить идентичности** — GhostGPT сохраняет «тебя» целиком, а не только поведение.

## Что уже есть (используй)
- rust_core/src/registry_manager.rs (Hybrid Registry)
- docs/LCE_IN_LS.md (LCE v1)
- https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP (LTP canon)
- https://github.com/safal207/Living-Relational-Identity-LRI (LRI invariants, emotional-drift, stabilizer, resonance map)
- codex/ + AgentLoop + qwen_handler.py

## Что нужно сделать

### 1. Расширение registry_manager.rs (v1.3)
Добавь метод:

```rust
fn save_causal_trace(&self, cause: String, solution: String, lce: PyObject, ltp_trace: PyObject, lri_core: PyObject, confidence: f32) -> PyResult<()> {
    // сохраняет JSON-line с LCE + LTP + LRI-Core
    // rolling max 50
}
```

### 2. Python-интеграция
В `python/modules/llm/qwen_handler.py`:

```python
def save_causal_trace(cause: str, solution: str, lce: dict, ltp_trace: dict, lri_core: dict, confidence: float = 0.92):
    reg = get_registry_manager()
    if reg:
        reg.save_causal_trace(cause, solution, lce, ltp_trace, lri_core, confidence)
        save_to_codex({**lce, "ltp_trace": ltp_trace, "lri_core": lri_core, "event_type": "causal_trace"})
```

В AgentLoop после успешного ответа:
```python
lri_core = {  # LRI invariants + emotional state
    "invariants": ["non_reductive", "consent_first"],
    "emotional_drift": 0.12,
    "resonance_map": {"focus": 0.88},
    "stabilizer": "active"
}
save_causal_trace(question, result, lce, ltp_trace, lri_core, 0.92)
```

### 3. Структура хранения
- Registry: `CausalMemory` — JSON-line с LCE + LTP + LRI-Core
- codex/causal_memory/ — полные JSON-трасы + index

#### Пример записи (JSON):
```json
{
  "ts": "2026-02-23T14:30:00Z",
  "cause": "What is 2+2?",
  "solution": "4",
  "confidence": 0.92,
  "lce": {
    "v": 1,
    "intent": {"type": "answer", "goal": "What is 2+2?"},
    "qos": {"coherence": 0.94}
  },
  "ltp_trace": {
    "thread_id": "thread-123",
    "drift": 0.05
  },
  "lri_core": {
    "invariants": ["non_reductive", "consent_first"],
    "emotional_drift": 0.12,
    "resonance_map": {"focus": 0.88},
    "stabilizer": "active"
  }
}
```

### 4. Обновления документации
- Добавить в `codex/windows_context.md`: «+ Causal Temporal Memory v1.3 + LCE + LTP + LRI»
- В `WEB4_ROADMAP.md` (6.5):
  ```markdown
  - [ ] Causal Temporal Memory v1.3 + LCE + LTP + LRI Integration (living identity + verifiable thread)
  ```

### 5. Чек-лист
- [ ] registry_manager.rs расширен
- [ ] save_causal_trace сохраняет LCE + LTP + LRI-Core
- [ ] В regedit видно LRI invariants
- [ ] Replay работает с LRI данными
- [ ] Обновлены md-файлы

## Acceptance Criteria
- Запись < 3 мс
- Полный LRI-Core в каждой записи
- Emotional-drift из LRI используется в coherence
- Готово к Web4 Mesh и Android-компаньону

Статус: В работе | Deadline: 8 часов
После выполнения — отметь **[DONE]**.

Codex Agent, вперёд. Строим **живую идентичность**.
