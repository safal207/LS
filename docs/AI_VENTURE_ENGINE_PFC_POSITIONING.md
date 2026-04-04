# AI Venture Engine + Portfolio Flow Controller (PFC)

## 1) Что это и зачем

**AI Venture Engine с Portfolio Flow Controller (PFC)** — это операционный слой для запуска и управления портфелем AI-продуктов, который решает ключевую ловушку: **Idea Flood vs Execution Bottleneck**.

Коротко: система не просто генерирует идеи, а **жестко управляет входом в исполнение, капиталом и стадиями развития проектов**.

---

## 2) Проблема, которую решаем

Большинство AI-систем быстро приходят к перекосу:

- идей и гипотез слишком много;
- команда/агенты и бюджет ограничены;
- проекты стартуют хаотично;
- капитал размазывается тонким слоем;
- kill/freeze решения принимаются поздно.

Результат: низкая конверсия в сильные продукты и падение ROI портфеля.

---

## 3) Решение: позиционирование продукта

### Категория

**AI-native venture operating system** (операционная система для AI-венчурного портфеля).

### One-liner

**PFC превращает поток AI-идей в управляемый портфель проектов с контролируемым риском, скоростью и доходностью.**

### Value proposition

- **Для founders/операторов**: прозрачные правила, куда идет капитал и почему.
- **Для продуктовых команд**: ясные gate-критерии и приоритеты исполнения.
- **Для инвесторов/экосистемы**: auditable ledger решений и дисциплина портфеля.

---

## 4) Кому это нужно (ICP)

1. **AI Studios / Venture Studios**
   - Запускают десятки гипотез, нуждаются в строгом admission и kill discipline.

2. **Продуктовые организации с internal startup model**
   - Нужны одинаковые правила отбора/масштабирования across teams.

3. **R&D и innovation offices**
   - Требуются быстрые эксперименты с контролем burn rate.

---

## 5) Ключевые дифференциаторы

1. **Admission Control по expected value**
   - В исполнение попадают только идеи, прошедшие порог ценности.

2. **WIP-limits на уровне портфеля**
   - Защита execution capacity от перегруза.

3. **Stage-Gate (pass / hold / freeze / kill)**
   - Управление жизненным циклом проекта по формальным метрикам.

4. **Capital Concentration**
   - Большая доля капитала у top-tier проектов, а не равномерный «размазанный» бюджет.

5. **Anti-thrashing controls**
   - Минимальные окна фокуса и ограничение реприоритизаций.

6. **Ledger traceability**
   - Каждое управленческое решение протоколируется для аудита и ретроспектив.

---

## 6) Маркетинговые сообщения (Messaging House)

### Core message

**Не просто “больше AI-идей”, а больше AI-проектов, которые доходят до scale и revenue.**

### Поддерживающие тезисы

- **Speed with discipline**: ускорение экспериментов без потери управляемости.
- **Capital efficiency**: приоритизация капитала по вероятности результата.
- **Execution clarity**: прозрачные правила принятия/заморозки/остановки.
- **Proof over hype**: решения принимаются по метрикам, а не по энтузиазму.

### Elevator pitch (30 сек)

> Мы построили AI Venture Engine с Portfolio Flow Controller — слой управления, который соединяет генерацию идей с реальным исполнением и капиталом. Система автоматически решает, какие гипотезы запускать, какие замораживать и какие масштабировать, чтобы команда не тонула в идеях, а портфель рос по доходности.

---

## 7) Что показывать на демо (чтобы фича была “видна всем”)

1. Поток: `idea -> validation -> admission -> gate -> allocation`.
2. На одном экране/в отчёте показывать:
   - сколько идей отклонено по EV;
   - сколько queued из-за WIP;
   - какие проекты frozen/killed и почему;
   - как изменилось распределение бюджета после rebalance.
3. Обязательно демонстрировать ledger trail по конкретному `project_id`.

---

## 8) KPI для продуктового и маркетингового трекинга

### Product KPI

- **Idea-to-Execution Ratio**
- **Scale Conversion Rate**
- **Kill Latency**
- **Capital Concentration Index**

### GTM KPI

- Количество команд, запустивших PFC-пайплайн в production-like режиме.
- Количество portfolio reviews с использованием ledger trace.
- Time-to-first-decision (от идеи до admission решения).

---

## 9) Пакетирование и оффер

### Internal rollout (внутри организации)

- **Phase 1**: прозрачный admission + отчетность по отказам/очередям.
- **Phase 2**: stage-gate + freeze/kill discipline.
- **Phase 3**: rebalance + концентрация капитала + регулярные portfolio reviews.

### Внешний оффер (для партнёров)

- **Pilot 4–6 недель**: внедрение на ограниченном наборе гипотез.
- Измеримые цели пилота:
  - снижение хаотичных стартов;
  - сокращение kill latency;
  - рост доли капитала в high-performing проектах.

---

## 10) Контент для публичного позиционирования

### Заголовки

- **“From Idea Flood to Portfolio Discipline”**
- **“AI Venture Engine: Scale Ideas Without Breaking Execution”**
- **“Portfolio Flow Controller: Operating System for AI Venture Throughput”**

### Короткий public description

**AI Venture Engine + PFC — это инфраструктура, которая превращает AI-генерацию идей в управляемый венчурный конвейер: строгий вход в исполнение, метрико-ориентированные stage-gates и концентрация капитала на победителях.**

---

## 11) Ссылки на связанные документы

- [Idea Flood vs Execution Bottleneck](./AI_VENTURE_ENGINE_IDEA_FLOOD_VS_EXECUTION_BOTTLENECK.md)
- [ТЗ: Portfolio Flow Controller](./AI_VENTURE_ENGINE_PORTFOLIO_FLOW_CONTROLLER_TZ.md)
- [E2E Simulation Guide](./AI_VENTURE_ENGINE_PFC_E2E_SIMULATION.md)

---

## 12) Быстрый старт для демонстрации

```bash
PYTHONPATH=python python python/examples/pfc_portfolio_simulation.py
```

Эта демонстрация показывает базовый цикл решений PFC и итоговое состояние портфеля.
