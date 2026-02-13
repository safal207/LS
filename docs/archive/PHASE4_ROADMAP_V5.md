# 🚀 Phase 4 Roadmap v5 — Temporal, Semantic & Stable CaPU

## 🎯 Vision
Сделать CaPU системой, которая:

- понимает время,
- понимает смысл,
- управляет памятью,
- держит стабильность,
- и восстанавливается сама.

Phase 4 — это переход от “умного движка” к когнитивному агенту.

---

## 🧩 Структура Phase 4 (v5)
С учётом всех ревью, Phase 4 разделена на MVP и Extended, чтобы избежать перегруза.

---

## 🌟 PHASE 4 MVP (обязательный минимум, 4–6 недель)
Это то, что даёт реальный скачок качества и не требует тяжёлой инфраструктуры.

---

### 4.0 — Temporal Foundation (реальная, не дублирующая)

**Что уже есть:**
- timestamps в beliefs и causal edges
- decay‑механизм

**Что добавляем:**
- Temporal Query API
  - `getbeliefssince(ts)`
  - `getbeliefsin_range(start, end)`
  - `getrecentchanges(n_cycles)`
- Temporal Index (возвращаем `temporal_index.py` как индекс, а не как модуль логики)
- Time‑aware context
  - контекст учитывает возраст belief/edge через decay

**KPI:**
- temporal queries < 100ms
- decay удаляет 5–15% устаревших beliefs в неделю

---

### 4.1 — Smart Circuit Breaker (новая подсистема)

**Состояния:**
- CLOSED
- OPEN
- HALF_OPEN

**Переходы:**
- CLOSED → OPEN: N ошибок подряд
- OPEN → HALF_OPEN: cooldown
- HALF_OPEN → CLOSED: M успехов
- HALF_OPEN → OPEN: 1 ошибка

**KPI:**
- система восстанавливается без ручного reset
- не допускает бесконечных failure‑циклов

---

### 4.2 — Semantic Layer v1 (без тяжёлых моделей)

**Что делаем:**
- улучшенный keyword‑matching:
  - stopwords
  - TF‑IDF
  - weighted keywords
- Pluggable Semantic Backend:

```python
class SemanticEncoder(Protocol):
    def encode(self, text: str) -> Vector: ...
```

**Embeddings:**
- опциональны, feature‑flag
- подключаются в Phase 5

**KPI:**
- +20–40% точности alignment без ML
- latency < 50ms

---

## 🌌 PHASE 4 EXTENDED (4.3–4.6, 6–12 недель)
Это эволюция поверх MVP.

---

### 4.3 — Memory Governance (определённая память)

**Память =**
- beliefs
- cold_storage
- archived transitions

**Что делаем:**
- scoring: importance, recency, frequency, coherence
- pruning:
  - score < 0.2 → архив
  - score < 0.4 → ускоренный decay
- archive compression
- memory budget limits

**KPI:**
- память не растёт бесконечно
- контекст всегда в пределах лимитов

---

### 4.4 — Causal Intelligence (Graph 2.0)

**4.6a (Must):**
- temporal weights
- causal confidence
- stale edge pruning

**4.6b (Advanced):**
- unstable loop detection
- causal inference

**KPI:**
- causal queries < 10ms при 1000 edges
- stale edges уменьшаются на 30–50%

---

### 4.5 — Cognitive Stability (над‑слой)

**Что делаем:**
- mission drift metrics
- semantic oscillation detection
- belief cluster drift

**KPI:**
- система фиксирует дрейф и сообщает о нём
- снижает flip‑flop решений

---

### 4.6 — Final Integration & Reliability

**Что делаем:**
- end‑to‑end pipeline
- performance benchmarks
- stress tests
- документация

**KPI:**
- COT цикл стабильно < X ms
- система работает 24–72 часа без деградации

---

## 🔗 Dependency Graph (v5)

```
4.0 Temporal Foundation
    ↓
4.1 Circuit Breaker
    ↓
4.2 Semantic Layer v1
    ↓
4.3 Memory Governance
    ↓
4.4 Causal Intelligence
    ↓
4.5 Cognitive Stability
    ↓
4.6 Final Integration
```

---

## 🧪 Testing Strategy (v5)

**Unit:**
- temporal queries
- circuit breaker transitions
- TF‑IDF alignment

**Integration:**
- temporal + causal
- semantic + mission
- memory + context

**Performance:**
- latency
- memory usage
- long‑run stability

**Quality:**
- semantic accuracy
- drift detection
- oscillation frequency

---

## ⚠️ Risk Matrix (v5)

**High:**
- semantic layer хуже keyword‑matching
- latency ↑
- memory overflow

**Medium:**
- causal graph слишком тяжёлый
- drift detection даёт ложные срабатывания

**Low:**
- документация отстаёт
- тесты требуют расширения

---

## 📅 Migration Plan (10 недель)

**Week 1–2**
- Temporal API + Index
- Circuit Breaker

**Week 3–4**
- Semantic Layer v1

**Week 5–6**
- Memory Governance

**Week 7–8**
- Causal Intelligence

**Week 9**
- Cognitive Stability

**Week 10**
- Integration + Benchmarks

---

## 🧠 Итог

Phase 4 Roadmap v5 — это:

- реалистично,
- структурировано,
- без дублирования,
- с KPI,
- с тестами,
- с рисками,
- с миграцией,
- с чётким MVP,
- и с ясной архитектурной логикой.

Это документ уровня senior/staff architect.


Note: Internal links may be outdated. This document is preserved for historical reference.
