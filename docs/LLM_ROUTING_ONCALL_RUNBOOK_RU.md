# LLM Routing On-Call Runbook (RU)

Цель: быстрые, безопасные действия при деградации LLM роутинга в проде.

## 1. Быстрый triage (5 минут)

Проверь в порядке приоритета:

1) `route.stats.fallback_total` резко вырос?  
2) `route.stats.backend_failure_total` у конкретного backend растет?  
3) В `route.explain.scores` появились `breaker_open=true` и/или `unhealthy=true`?  
4) Ошибки клиентам: timeout / empty / provider errors.

Если 1+2 подтверждаются — переходи к mitigation.

---

## 2. Mitigation (без остановки сервиса)

### A) Снизить риск быстро

- Переключи runtime policy на более стабильную:

```python
lm.update_routing_controls({
  "runtime_policy": "latency_optimized",
  "runtime_health_thresholds": {"error_rate": 0.08, "latency_ms": 5000},
})
```

### B) Уйти в безопасный режим

- Если эксперимент шел в `ab`, временно вернуть `primary`:

```python
lm.apply_rollout_stage("baseline")
```

### C) Если нужно сравнение без риска

- Перейти в `shadow`:

```python
lm.apply_rollout_stage("shadow")
```

---

## 3. Эскалация

Эскалируй, если выполняется хотя бы одно:

- error rate > 5% более 10 минут;
- p95 вырос > 2x относительно baseline;
- >20% запросов уходят в fallback 15+ минут;
- два и более backend имеют breaker-open одновременно.

---

## 4. Восстановление

После стабилизации:

1) Верни `runtime_policy` и thresholds к стандартным.
2) Проверяй 30–60 минут тренд по `fallback_total` и `backend_failure_total`.
3) Возвращай A/B постепенно: `ab_5` -> `ab_10` -> `ab_20`.

---

## 5. Postmortem checklist

- [ ] Время обнаружения, время mitigation, время восстановления.
- [ ] Какие controls применялись (`runtime_policy`, thresholds, stage).
- [ ] Какие backend деградировали и почему.
- [ ] Какие алерты сработали / не сработали.
- [ ] Что добавить: новый alert, тест, или более строгий threshold.

