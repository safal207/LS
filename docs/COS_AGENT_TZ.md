# Когнитивная операционная система локального агента (COS‑Agent)
**Версия:** 1.0 — Архитектура от железа до интернета  
**Статус:** техническое задание (ТЗ)

---

## 1. Цель системы
Создать локального когнитивного агента, который:

- работает без дата‑центров
- адаптируется к железу и ядру
- принимает решения через формальные протоколы
- учится без галлюцинаций
- взаимодействует с человеком и интернетом безопасно
- формирует причинную память
- обладает когнитивными состояниями (присутствие, доверие, нагрузка)

---

## 2. Общая архитектура

```
┌──────────────────────────────────────────────┐
│                Интернет (LIP)                │
│  Internet Trust Protocol / Anti‑Hallucination│
└───────────────────────────┬──────────────────┘
                            │
┌───────────────────────────▼──────────────────┐
│                Человек                        │
│  Feedback / Correction / Validation           │
└───────────────────────────┬──────────────────┘
                            │
┌───────────────────────────▼──────────────────┐
│                Модели (LLM/STT/etc)          │
│  AdaptiveEngine / Model Selection             │
└───────────────────────────┬──────────────────┘
                            │
┌───────────────────────────▼──────────────────┐
│   Unified Cognitive Loop (Python)            │
│   LPI / LTP / LRI / Scheduler / DMP          │
│   Causal Memory / Narrative / Identity       │
└───────────────────────────┬──────────────────┘
                            │
┌───────────────────────────▼──────────────────┐
│   Kernel Runtime (Rust)                      │
│   eBPF / perf / syscalls / NUMA / topology   │
└───────────────────────────┬──────────────────┘
                            │
┌───────────────────────────▼──────────────────┐
│                 Железо                        │
└──────────────────────────────────────────────┘
```

---

## 3. Слои системы

### 3.1. Hardware Layer (Python + Rust)
**Задачи:**
- сбор метрик CPU, RAM, IO, температуры
- NUMA‑топология
- CPU‑топология
- передача данных в когнитивный слой

**Rust‑часть:**
- eBPF
- perf counters
- syscalls
- context switches
- HPI/CLI
- IPC через UDS

**Python‑часть:**
- HardwareMonitor
- NUMA parser
- Topology parser

---

### 3.2. Kernel Runtime (Rust → Python)
**Rust:**
- сбор телеметрии ядра
- нормализация сигналов
- отправка JSON в Python

**Python:**
- KernelSensorMonitor
- KernelSensorListener
- KernelRuntime

---

### 3.3. LRI — Local Resource Intelligence (Python)
**Функции:**
- вычисление когнитивной нагрузки
- определение состояния: stable / elevated / overload
- теги: cpu_bound, io_bound, thermal_risk и т.п.
- влияние на стратегию и scheduler

---

### 3.4. LTP — Liminal Thread Protocol (Python)
**Функции:**
- доверие к потокам
- состояния: untrusted → probing → trusted → quarantined
- реакция на kernel/LRI
- влияние на attention и допуск к моделям

---

### 3.5. LPI — Liminal Presence Interface (Python)
**Функции:**
- состояние присутствия агента
- focused / diffuse / overloaded / engaged
- влияние на стратегию и обучение

---

### 3.6. Scheduler (Python)
**Функции:**
- управление потоками
- attention и приоритеты
- реакция на LTP, LRI, kernel
- NUMA / CPU‑affinity

---

### 3.7. AdaptiveEngine (Python)
**Функции:**
- выбор стратегии: aggressive / balanced / conservative / ultra_conservative
- приоритет: kernel → LRI → presence → hardware → risks

---

### 3.8. DMP — Decision Memory Protocol (Python)
**Функции:**
- запись каждого решения
- причины и альтернативы
- последствия
- состояние системы
- доверие (LTP), присутствие (LPI), нагрузка (LRI), kernel‑сигналы

---

### 3.9. Causal Memory (Python)
**Функции:**
- причинные связи
- объяснение ошибок
- прогнозирование последствий
- обучение на опыте

---

### 3.10. Unified Cognitive Loop (Python)
**Функции:**
- главный цикл
- сбор контекста
- выбор модели
- выполнение
- запись в память
- обновление состояний

---

## 4. Интернет‑протокол (LIP — Liminal Internet Protocol)
**Цель LIP:**
- обучение без галлюцинаций
- проверка источников
- доверие к интернету
- причинная запись решений
- безопасное обновление знаний

### 4.1. InternetTrustProfile
**Состояния:**
- untrusted
- probing
- trusted
- blacklisted

**Переходы:**
- новый источник → untrusted
- несколько совпадений → probing → trusted
- ложь → blacklisted

### 4.2. Internet DMP
Каждый факт из интернета — это решение с записью:
- источник
- альтернативы
- доверие
- последствия
- подтверждение человеком

### 4.3. Anti‑Hallucination Loop
Алгоритм:
1. собрать несколько источников
2. оценить доверие
3. сравнить
4. принять только если ≥2 trusted совпадают
5. записать в DMP
6. отложенная проверка

### 4.4. Человек в контуре
Человек:
- подтверждает
- корректирует
- отклоняет

Все действия фиксируются в DMP.

### 4.5. Ограничения обучения
Обучение допустимо только если:
- LRI < 0.5
- LPI = focused или engaged
- нет kernel_overload

---

## 5. Где Python, где Rust

| Слой | Python | Rust |
|------|--------|------|
| HardwareMonitor | ✔ | |
| Kernel Runtime | ✔ | ✔ |
| eBPF / perf | | ✔ |
| KernelSensorMonitor | ✔ | |
| LRI | ✔ | |
| LTP | ✔ | |
| LPI | ✔ | |
| Scheduler | ✔ | |
| AdaptiveEngine | ✔ | |
| DMP | ✔ | |
| Causal Memory | ✔ | |
| Unified Loop | ✔ | |
| Internet Protocol (LIP) | ✔ | |

Rust = сенсорика и ядро  
Python = когнитивная логика

---

## 6. Следующие шаги
- собрать единый финальный репозиторий
- написать архитектурную диаграмму (SVG)
- добавить код LIP
- собрать полный патч для проекта
