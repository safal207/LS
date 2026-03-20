# SmartEar

Когнитивный слой между STT и AgentLoop. Исправляет ошибки распознавания IT-терминов, фильтрует шум и со временем обучается на собственных решениях.

```
AudioIngestion → SpeechToText → [stt_queue]
    → SmartEar → [llm_queue]
        → AgentLoop
```

## Содержание

- [Как это работает](#как-это-работает)
- [Установка зависимостей](#установка-зависимостей)
- [Конфигурация](#конфигурация)
- [Доменные словари](#доменные-словари)
- [Жизненный цикл: от первого запуска до ML-модели](#жизненный-цикл)
- [Структура файлов](#структура-файлов)
- [EventBus топики](#eventbus-топики)
- [Feedback loop](#feedback-loop)
- [Мониторинг и дашборд](#мониторинг-и-дашборд)
- [Скрипты](#скрипты)
- **[📘 SmartEar ML Production Upgrade (2026-03-20)](docs/SMARTEAR_ML_PRODUCTION_UPGRADE.md)** ← LightGBM, calibration, validation gate

---

## Как это работает

Каждый STT-item проходит три стадии:

### 1. FilterStage — выбрасывает мусор

Считает composite score:

```
composite = 0.5 × ASR_confidence + 0.25 × context_match + 0.25 × vocab_match
```

Если score ниже порога — item отбрасывается. Порог автоматически повышается, если Amygdala сигнализирует о высокой когнитивной нагрузке.

### 2. HypothesisStage — исправляет неуверенные слова

Whisper возвращает вероятность на каждое слово. Слова с `probability < 0.50` сравниваются с доменным словарём через `difflib.SequenceMatcher`. Если похожесть выше порога — слово заменяется. Высокоуверенные слова не трогаются.

### 3. SelectionStage — выбирает финальный текст

Если ML-модель загружена и не задетектирован drift:

| Вероятность | Решение |
|---|---|
| `prob > 0.70` | corrected |
| `prob < 0.30` | original |
| `0.30 ≤ prob ≤ 0.70` | эвристика (corrected побеждает если vocab-score выше на `selection_margin`) |

Если модели нет — только эвристика.

---

## Установка зависимостей

Базовый SmartEar работает без дополнительных зависимостей (использует `difflib` из stdlib).

ML-компоненты (обучение, drift detection, auto-retrain) требуют scikit-learn:

```bash
pip install scikit-learn
```

Если scikit-learn не установлен — SmartEar автоматически переключается на эвристику. Никаких ошибок при запуске не будет.

---

## Конфигурация

Все параметры задаются в основном конфиге приложения в секции `smart_ear`:

```yaml
smart_ear:
  # Веса composite score (сумма должна быть 1.0)
  weights:
    asr: 0.50          # вес ASR confidence
    context: 0.25      # вес совпадения с контекстом
    vocab: 0.25        # вес совпадения с доменным словарём
  threshold: 0.25      # минимальный composite для прохождения FilterStage
  low_word_prob: 0.50  # слова ниже этой вероятности идут на коррекцию
  vocab_similarity: 0.60    # порог схожести для PhoneticCorrector
  selection_margin: 1       # corrected должен обогнать original на это значение
  vocab_min_length: 3       # минимальная длина термина для добавления в словарь
  vocab_refresh_every: 60   # пересчёт словаря из CausalMemory каждые N items
  domain_packs: []          # подключаемые словарные паки, например: ["web_dev", "devops"]
  audit_log: ""             # путь к JSONL-логу всех решений (пусто = выключено)
  audit_max_mb: 10          # ротация лога при превышении размера
```

### Параметры AutoRetrain (только через код)

```python
SmartEar(
    ...
    dataset_log_path="data/smart_ear_dataset.jsonl",  # включает сбор датасета
    auto_retrain=True,       # включает фоновое переобучение
    retrain_every=50,        # переобучать после каждых N новых примеров
    metrics_window=200,      # размер окна для rolling metrics
)
```

---

## Доменные словари

SmartEar поставляется с четырьмя готовыми паками:

| Пак | Содержимое |
|---|---|
| `web_dev` | React, Vue, Angular, TypeScript, Next.js, GraphQL, PostgreSQL... |
| `devops` | Docker, Kubernetes, Terraform, GitHub Actions, Prometheus... |
| `crypto` | Ethereum, Solidity, DeFi, NFT, MetaMask, zkRollup... |
| `qa` | pytest, Playwright, Jest, TDD, load test, Locust... |

Каждый пак включает русские фонетические варианты (`"реакт"`, `"докер"`, `"кубернетес"`).

Подключение в конфиге:

```yaml
smart_ear:
  domain_packs: ["web_dev", "devops"]
```

### Добавление своего пака

Создайте файл `python/modules/stt/domain_packs/my_pack.py`:

```python
VOCAB = [
    "MyTerm", "AnotherTerm",
    "мойтермин",  # русский вариант
]
```

Зарегистрируйте в `python/modules/stt/domain_packs/__init__.py`:

```python
from .my_pack import VOCAB as _MY_PACK

_REGISTRY = {
    ...
    "my_pack": _MY_PACK,
}
```

---

## Жизненный цикл

### Фаза 1 — Первый запуск (эвристика)

Модели нет, система работает на правилах. Whisper + PhoneticCorrector уже исправляют очевидные ошибки (`"реак"` → `"React"`).

Чтобы начать собирать данные для обучения, включите `dataset_log_path` и `audit_log` в конфиге:

```python
SmartEar(
    ...
    audit_log_path="data/smart_ear_audit.jsonl",
    dataset_log_path="data/smart_ear_dataset.jsonl",
)
```

### Фаза 2 — Накопление данных

Каждый раз когда SmartEar принимает решение о коррекции, запись попадает в `dataset_log_path`. Особенно ценны записи из feedback loop — это gold labels.

Смотреть что накапливается:

```bash
wc -l data/smart_ear_dataset.jsonl   # количество примеров
cat data/smart_ear_audit.jsonl | python -m json.tool | head -50
```

### Фаза 3 — Первое обучение (минимум 20 примеров)

```bash
python python/modules/smart_ear/train_model.py \
    --dataset data/smart_ear_dataset.jsonl \
    --model models/smart_ear_model.pkl
```

Вывод покажет accuracy, precision, recall и веса признаков. Если accuracy низкая — нужно больше данных и больше feedback.

### Фаза 4 — Работа с ML-моделью

При следующем запуске SmartEar автоматически загрузит модель из `models/smart_ear_model.pkl`. SelectionStage переключится в 3-зонный режим.

### Фаза 5 — Автоматическое переобучение

Включите `auto_retrain=True`. AutoTrainer в фоне следит за ростом датасета и запускает переобучение в отдельном процессе без остановки системы. После переобучения модель hot-swap'ается.

```
Датасет вырос на 50 строк → subprocess: train_model.py → новый .pkl → load_model() → clear_drift()
```

---

## Структура файлов

```
python/modules/
├── stt/
│   ├── smart_ear.py          # оркестратор: FilterStage, HypothesisStage, SelectionStage
│   ├── phonetic.py           # PhoneticCorrector (difflib, без зависимостей)
│   └── domain_packs/
│       ├── __init__.py       # load_packs()
│       ├── web_dev.py
│       ├── devops.py
│       ├── crypto.py
│       └── qa.py
└── smart_ear/                # ML-подпакет
    ├── __init__.py
    ├── features.py           # extract_features() — pure function
    ├── decision_model.py     # SmartEarDecisionModel: load / predict / zone
    ├── train_model.py        # скрипт обучения (запускать вручную или через auto_trainer)
    ├── auto_trainer.py       # SmartEarAutoTrainer: фоновый watchdog
    └── metrics.py            # SmartEarMetrics: rolling window + drift detection

data/
└── smart_ear_dataset.jsonl   # обучающие примеры (генерируется автоматически)

models/
└── smart_ear_model.pkl       # обученная модель (в .gitignore)

scripts/
└── test_decision_model.py    # сравнение эвристики vs ML на реальных данных
```

---

## EventBus топики

| Топик | Когда | Payload |
|---|---|---|
| `smart_ear_selected` | Item прошёл все стадии | `{text, composite_confidence, source, corrections}` |
| `smart_ear_rejected` | FilterStage отбросил item | `{text, reason}` |
| `smart_ear_candidates` | После HypothesisStage | `{original, corrected, corrections, per_word_candidates}` |
| `smart_ear_feedback` | Пользователь исправил | `{original, correct, new_terms}` |
| `voice_detected` | VAD: тишина → голос | `{rms, timestamp}` |
| `silence_detected` | VAD: голос → тишина | `{rms, timestamp}` |

Значения `source` в `smart_ear_selected`:

- `original` — оставлен оригинальный текст
- `phonetic` — исправлено эвристикой
- `phonetic_ml` — исправлено ML-моделью

---

## Feedback loop

Самый быстрый способ научить систему новому термину:

```python
# Система услышала "реакт квери" вместо "React Query"
smart_ear.user_feedback(
    original_text="реакт квери",
    correct_text="React Query",
)
```

Что происходит:

1. `"React"` и `"Query"` добавляются в доменный словарь немедленно — следующее высказывание уже учтёт
2. Запись с меткой `chosen = "corrected"` добавляется в датасет как gold label
3. Событие публикуется в EventBus (`smart_ear_feedback`)

Feedback можно вызывать из UI, горячей клавиши или любого другого места.

---

## Мониторинг и дашборд

```python
metrics = smart_ear.get_metrics()
print(metrics)
```

```json
{
  "window_size": 145,
  "source_distribution": {
    "original": 89,
    "phonetic": 31,
    "phonetic_ml": 25
  },
  "correction_rate": 0.386,
  "avg_ml_confidence": 0.731,
  "feedback_rate": 0.021,
  "total_decisions": 512,
  "drift_detected": false,
  "drift_reason": null
}
```

**Drift detection** — система автоматически переключается на эвристику если:

- Средний `avg_ml_confidence` падает ниже `0.45`
- Доля feedback событий превышает `30%`

После успешного переобучения drift сбрасывается автоматически.

---

## Скрипты

### Обучение модели вручную

```bash
python python/modules/smart_ear/train_model.py

# С явными путями:
python python/modules/smart_ear/train_model.py \
    --dataset data/smart_ear_dataset.jsonl \
    --model models/smart_ear_model.pkl \
    --test-frac 0.2
```

### Сравнение эвристики и ML на реальных данных

```bash
python scripts/test_decision_model.py

# Больше примеров, фиксированный seed:
python scripts/test_decision_model.py --n 50 --seed 42
```

Вывод покажет side-by-side сравнение решений для каждого примера и итоговую точность обоих подходов.
