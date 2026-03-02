# Архитектурные слои GhostGPT / GhostGPT Architectural Layers (v2026.03)

Этот документ содержит полный каталог всех архитектурных слоев GhostGPT, обеспечивающих работу "живого" цифрового двойника.

---

## Каталог слоев / Layers Catalog

| № | Слой (Layer) | Ключевые компоненты (Key Components) | Ответственность (Responsibility) | Связи (Connections) | Статус (Status) |
|---|---|---|---|---|---|
| 1 | **Perception Layer** | `AudioIngestion`, `SpeechToText`, `InputParser` | Приём и первичная обработка text/audio/image. | → Memory, → Amygdala | Stable |
| 2 | **Memory System** | `MemoryService`, `CausalMemory`, `TemporalGraph` | Хранение STM/LTM, эпизодическая и семантическая память. | ↔ Reflection, ↔ Metabolism | Stable |
| 3 | **Reflection & Reasoning** | `ReflectionEngine`, `SilentReflection` | Генерация инсайтов, "тихая" рефлексия в фоне. | → Metabolism, → Lessons | Stable |
| 4 | **Amygdala (Emotional)** | `Amygdala`, `VisceralMemory`, `EndocrineSystem` | Эмоциональный баланс, резонанс, фантомные боли. | ↔ AgentLoop, ↔ Sleep | Stable |
| 5 | **Executive AgentLoop** | `AgentLoop`, `EventBus`, `_process_item` | Главный цикл, оркестрация всех процессов системы. | ↔ Все слои (All layers) | Stable |
| 6 | **Metabolism & Consolidation** | `MetabolismEngine`, `nutrient_pool`, `lessons` | Переработка "отходов" памяти в энергию роста и уроки. | → Axis, → Immunity | **NEW** |
| 7 | **Sleep & Homeostasis** | `SleepConfig`, `auto-sleep`, `wake_up` | Консолидация памяти, очистка и восстановление во сне. | ← AgentLoop, → Memory | **NEW** |
| 8 | **Growth Axis** | `Axis`, `feed_growth()`, `meritocratic_axis` | Укрепление "стержня" агента, рост осознанности. | ← Metabolism | Stable |
| 9 | **Immune & Safety** | `ImmuneMemory`, `Antibody`, `ReflexArc` | Защита от инъекций, перенос паттернов угроз в LTM. | ← Metabolism | Stable |
| 10 | **Dynamic Inference Router** | `ModelSizePolicy`, `RAMAwareSelector` | Выбор модели (Qwen3.5 0.8B/2B/4B) под железо. | → Perception, ← Sleep | **Planned** |
| 11 | **Hardware Abstraction** | `BackendAdapter` (vLLM, Ollama, MLX) | Абстракция вычислений и ускорения (GPU/NPU). | → Inference Router | Stable |
| 12 | **Human Interface & GUI** | `GhostGPT GUI`, `Animations`, `VisualFeedback` | Визуализация состояния (❤️, ♻️) и управление. | ↔ AgentLoop | Stable |

---

## Детальное описание слоев / Detailed Layer Description

### 1. Perception Layer (Слой восприятия)
*   **RU:** Отвечает за преобразование внешних сигналов в когнитивные объекты. Включает VAD (Voice Activity Detection) и STT.
*   **EN:** Responsible for converting external signals into cognitive objects. Includes VAD and STT.
*   **Code:** `python/modules/audio/audio_module.py`, `python/modules/stt/stt_module.py`.

### 2. Memory System (Система памяти)
*   **RU:** Гибридная система: Causal Graph (причинность), Temporal Graph (время) и Semantic Clusters.
*   **EN:** Hybrid system: Causal Graph (causality), Temporal Graph (time), and Semantic Clusters.
*   **Code:** `codex/causal_memory/memory.py`, `python/modules/hexagon_core/temporal_graph.py`.

### 3. Reflection & Reasoning (Слой рефлексии)
*   **RU:** Механизм самоанализа. Генерирует `last_silent_reflection`, когда агент находится в режиме "йоги".
*   **EN:** Self-analysis mechanism. Generates `last_silent_reflection` while in "yoga" mode.
*   **Code:** `python/modules/agent/loop.py` (`_maybe_enter_idle_yoga`).

### 4. Amygdala (Амигдала / Эмоциональное состояние)
*   **RU:** Регулятор состояний. Вычисляет резонанс (resonance) и блокирует опасные переходы.
*   **EN:** State regulator. Calculates resonance and blocks dangerous transitions.
*   **Code:** `codex/causal_memory/amygdala.py`, `codex/causal_memory/visceral.py`.

### 5. Executive AgentLoop (Исполнительный цикл)
*   **RU:** "Сердце" системы. Управляет очередями задач и переключением состояний (idle/thinking/sleep).
*   **EN:** The "heart" of the system. Manages task queues and state switching.
*   **Code:** `python/modules/agent/loop.py`.

### 6. Metabolism & Consolidation (Метаболизм и консолидация)
*   **RU:** **НОВЫЙ СЛОЙ.** Перерабатывает удаленные узлы графа и старые рефлексии в `nutrient_pool`.
*   **EN:** **NEW LAYER.** Recycles pruned graph nodes and old reflections into the `nutrient_pool`.
*   **Code:** `codex/causal_memory/metabolism.py`.

### 7. Sleep & Homeostasis (Сон и гомеостаз)
*   **RU:** **НОВЫЙ СЛОЙ.** Запускается автоматически после 1800с бездействия. Выполняет `digest_old_reflections`.
*   **EN:** **NEW LAYER.** Triggers automatically after 1800s of idleness. Executes `digest_old_reflections`.
*   **Code:** `python/modules/agent/sleep_config.py`, `AgentLoop._enter_sleep_mode()`.

### 8. Growth Axis (Ось роста)
*   **RU:** Накопительный эффект метаболизма. Увеличивает `harmony_bonus` и общую стабильность системы.
*   **EN:** Cumulative effect of metabolism. Increases `harmony_bonus` and overall system stability.
*   **Code:** `python/modules/hexagon_core/temporal_graph.py` (`strengthen_strong_links`).

### 9. Immune & Safety System (Иммунная система)
*   **RU:** Адаптивная защита. Создает "антитела" (antibodies) на основе заблокированных инъекций.
*   **EN:** Adaptive defense. Creates "antibodies" based on blocked injections.
*   **Code:** `codex/causal_memory/immune.py`, `codex/causal_memory/reflex.py`.

### 10. Dynamic Inference Router (Динамический роутер инференса)
*   **RU:** **ПЛАНИРУЕТСЯ.** Будет выбирать между Qwen3.5-0.8B (быстрый) и 7B (глубокий) в зависимости от контекста.
*   **EN:** **PLANNED.** Will choose between Qwen3.5-0.8B (fast) and 7B (deep) depending on context.
*   **Code:** `python/modules/llm/ram_model_selector.py` (v1 base).

### 11. Hardware Abstraction (Абстракция железа)
*   **RU:** Позволяет запускаться на vLLM, Ollama или напрямую через MLX на Apple Silicon.
*   **EN:** Allows running on vLLM, Ollama, or directly via MLX on Apple Silicon.
*   **Code:** `python/modules/llm/llm_module.py`.

### 12. Human Interface & GUI (Интерфейс и GUI)
*   **RU:** Визуальный слой. Отображает пульсацию кровеносной системы (Bloodstream) и прогресс метаболизма.
*   **EN:** Visual layer. Displays bloodstream pulsing and metabolism progress.
*   **Code:** `GhostGPT/modules/gui.py`.
