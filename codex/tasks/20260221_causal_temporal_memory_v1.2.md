# Задача Codex Agent: Causal Temporal Memory + LCE + LTP Integration v1.2
Phase: 6.5 Runtime Hardening+ → 7.0 Platform Expansion (Temporal Graph + Liminal Thread)
Дата: 2026-02-21
Владелец: safal207
Приоритет: MUST HAVE

## Цель
Создать в HKCU\Software\LS\GhostGPT\CausalMemory постоянную память, где каждое «причина → решение» хранится:
- вместе с полным LCE (из docs/LCE_IN_LS.md)
- вместе с LTP trace (из https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-)
- с invariants, drift, admissible futures и deterministic replay

Это превращает память в **живую auditable нить** — GhostGPT сможет replay’ить прошлые контексты, измерять drift и сохранять verifiable continuity.

## Что уже есть (используй)
- rust_core/src/registry_manager.rs (Hybrid Registry)
- docs/LCE_IN_LS.md (LCE v1)
- https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP- (LTP canon, invariants, traces, inspector)
- codex/ + AgentLoop + qwen_handler.py

## Что нужно сделать

### 1. Расширение registry_manager.rs (v1.2)
Добавь метод:

```rust
fn save_causal_trace(&self, cause: String, solution: String, lce: PyObject, ltp_trace: PyObject, confidence: f32) -> PyResult<()> {
    // сохраняет JSON-line с LCE + LTP trace (invariants, drift, replay_data)
    // rolling max 50
}
```

### 2. Python-интеграция
В qwen_handler.py:

```python
def save_causal_trace(cause: str, solution: str, lce: dict, ltp_trace: dict, confidence: float = 0.9):
    reg = get_registry_manager()
    if reg:
        reg.save_causal_trace(cause, solution, lce, ltp_trace, confidence)
        save_to_codex({**lce, "ltp_trace": ltp_trace, "event_type": "causal_trace"})
```

В AgentLoop после успешного ответа:
```python
ltp_trace = {  # из LTP SDK или простая структура
    "thread_id": current_thread,
    "invariants": [...],
    "drift": 0.12,
    "admissible_futures": ["A", "B"]
}
save_causal_trace(question, result, lce, ltp_trace, 0.92)
```

### 3. Структура хранения
- Registry: `CausalMemory` (REG_MULTI_SZ) — JSON-line с LCE + LTP
- codex/causal_memory/ — полные JSON-трасы + index

### 4. Обновления документации
- Добавить в `codex/windows_context.md`: «+ Causal Temporal Memory v1.2 + LCE + LTP»
- В `WEB4_ROADMAP.md` (6.5):
  ```markdown
  - [ ] Causal Temporal Memory v1.2 + LCE + LTP Integration (verifiable thread + replay)
  ```

### 5. Чек-лист
- [ ] registry_manager.rs расширен
- [ ] save_causal_trace сохраняет LCE + LTP
- [ ] В regedit видно LTP traces
- [ ] Replay работает через LTP inspector
- [ ] Обновлены md-файлы

## Acceptance Criteria
- Запись < 3 мс
- Полный LTP trace в каждой записи
- Drift detection из LTP используется в coherence
- Готово к Web4 Mesh replay

Статус: В работе | Deadline: 8 часов
После выполнения — отметь **[DONE]**.

Codex Agent, вперёд. Строим verifiable память с LTP.
