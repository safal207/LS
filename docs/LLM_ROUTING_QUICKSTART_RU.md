# LLM Routing — быстрый гайд (RU)

Этот документ — практический quickstart по текущему роутеру `LLMBackendRouter`.

## Что умеет роутер сейчас

- Выбор backend по `intent` и policy (`balanced`, `latency_optimized`, `cost_optimized`).
- Учет health-метрик (`latency_ms`, `error_rate`, `load`, `cost`).
- Circuit breaker (временная демоция нестабильного backend).
- Fallback-цепочка на случай ошибок.
- Режимы экспериментов: `ab` и `shadow`.
- Explainability (`response.raw["route"]["explain"]`) + counters (`response.raw["route"]["stats"]`).

---

## 1) Минимальный запуск

```python
from modules.llm.backends.router import build_llm_backend

router = build_llm_backend(
    backend="cloud",
    fallback_chain="local",
)

resp = router.generate(
    messages=[{"role": "user", "content": "Ответь быстро"}],
    metadata={
        "intent": "realtime",
        "policy": "latency_optimized",
    },
)

print(resp.text)
print(resp.raw["route"]["explain"])
```

---

## 2) Контракт `metadata`

### Базовые поля

```python
metadata = {
  "intent": "realtime",           # optional: можно не указывать, есть auto-infer
  "policy": "balanced",           # balanced | latency_optimized | cost_optimized
  "pin_primary": False,            # если True, primary всегда остается первым
}
```

### Health fields

```python
metadata.update({
  "backend_health": {
    "cloud": {"latency_ms": 350, "error_rate": 0.03, "load": 0.50, "cost": 0.80},
    "local": {"latency_ms": 180, "error_rate": 0.01, "load": 0.20, "cost": 0.10},
  },
  "health_thresholds": {
    "error_rate": 0.10,
    "latency_ms": 8000,
  },
})
```

### Breaker fields

```python
metadata.update({
  "breaker_failure_threshold": 3,
  "breaker_cooldown_seconds": 30,
})
```

### Experiment fields

```python
metadata.update({
  "routing_mode": "ab",           # primary | ab | shadow
  "request_id": "trace-42",       # для стабильного bucket в A/B
  "ab_variant_ratio": 0.20,         # 20% трафика на variant policy
  "ab_variant_policy": "cost_optimized",
  "shadow_policy": "cost_optimized",
})
```

---

## 3) Что писать в логи/метрики

Рекомендуется сохранять:

- `route.explain.policy`, `route.explain.intent`
- `route.explain.effective`
- `route.explain.ab_variant_selected`
- `route.stats.requests_total`
- `route.stats.fallback_total`
- `route.stats.ab_variant_selected_total`
- `route.stats.shadow_evaluations_total`
- `route.stats.backend_success_total`, `route.stats.backend_failure_total`

Это даст понятную картину: кто выбирался, почему и как система ведет себя при сбоях.

---

## 4) Режимы rollout

### Этап A — baseline

- `routing_mode=primary`
- `policy=balanced`
- собираем explain + stats без агрессивных изменений

### Этап B — shadow

- `routing_mode=shadow`
- сравниваем `explain.effective` (base vs shadow)
- убеждаемся, что новая policy не ухудшает latency/error

### Этап C — A/B

- `routing_mode=ab`
- `ab_variant_ratio=0.05` → `0.10` → `0.20`
- мониторим p95/error/cost

### Этап D — rollout

- если KPI стабильны: поднимаем долю и делаем variant policy основной

---

## 5) Runtime overrides (оперативное управление)

```python
router.set_runtime_overrides(
    policy="cost_optimized",
    health_thresholds={"error_rate": 0.08, "latency_ms": 5000},
)

# ...

router.clear_runtime_overrides()
```

Когда полезно:

- во время инцидента быстро ужесточить пороги;
- временно сдвинуть политику в cost/latency;
- вернуть систему в штатный режим после стабилизации.

### Через `LanguageModel` (прикладной API)

```python
lm.update_routing_controls({
    "routing_mode": "ab",
    "ab_variant_ratio": 0.10,
    "ab_variant_policy": "cost_optimized",
    "policy": "balanced",
    "runtime_policy": "latency_optimized",
    "runtime_health_thresholds": {"error_rate": 0.08},
})

snapshot = lm.get_routing_observability()
print(snapshot["defaults"])
print(snapshot["last_explain"])
print(snapshot["stats"])
```

### Быстрые rollout-профили

```python
lm.apply_rollout_stage("baseline")  # primary + balanced
lm.apply_rollout_stage("shadow")    # shadow compare
lm.apply_rollout_stage("ab_5")
lm.apply_rollout_stage("ab_10")
lm.apply_rollout_stage("ab_20")
```

---

## 6) Troubleshooting

### Симптом: слишком частый fallback

Проверь:

- корректность `backend_health`;
- не слишком ли строгие `health_thresholds`;
- не открыт ли breaker у primary backend.

### Симптом: A/B «не включается»

Проверь:

- `routing_mode=ab`;
- `ab_variant_ratio > 0`;
- наличие `request_id`/`trace_id`/`user_id` (для стабильного bucket).

### Симптом: shadow не виден

Проверь:

- `routing_mode=shadow`;
- наличие `shadow_policy`;
- наличие `response.raw["route"]["explain"]["shadow"]`.

---

## 7) Чеклист готовности к прод

- [ ] Включены метрики по route explain/stats.
- [ ] Есть алерты на error rate / p95 / fallback spikes.
- [ ] Пройдены shadow сравнения.
- [ ] Пройден A/B с целевыми KPI.
- [ ] Есть runbook и ответственный on-call.

Дополнительно: отдельный on-call документ `docs/LLM_ROUTING_ONCALL_RUNBOOK_RU.md`.
