# GhostGPT v1.1 (2026-03-05)

## Architecture & Cognitive Layers
- **Full 12-Layer Stack**: Внедрена и задокументирована полная 12-слойная архитектура.
- **Metabolism & Consolidation**: Слой метаболизма (`Metabolism`) для переработки когнитивных "отходов" в `nutrient_pool`.
- **Sleep & Homeostasis**: Автоматический режим сна (1800с) для глубокой консолидации памяти и укрепления оси роста.
- **Immune & Safety**: Адаптивная иммунная память для блокировки инъекций и угроз без вызова LLM.

## Biological & Advanced Integration (Experimental)
- **Bloodstream Layer**: Синхронизация состояний амигдалы и фильтрация токсинов в реальном времени.
- **Self-Healing Soul**: Механизм автоматического восстановления состояния амигдалы при детекции аномалий через L-THREAD.

## Model Support
- **Qwen3.5 Small Series Ready**: Подготовка к интеграции моделей Qwen3.5 (0.8B, 2B, 4B, 9B).
- **Dynamic Model Policy**: Основа для адаптивного выбора размера модели в зависимости от RAM и сложности задачи.

# GhostGPT v1.0 (2026-02-27)

## Key Features
- Полностью локальный запуск (Ollama + Qwen2.5-7B / Phi-4-mini fallback)
- RAM-aware модельный выбор для слабого железа (Ryzen 5700U 16 ГБ)
- Интервью-копилот в GUI (GhostGPT) с Access Protocol (self-love, resonance)
- Console-режим для быстрого тестирования
- Temporal/causal memory + AgentLoop
- Resonance eval harness + LLM-as-Judge
- Circuit breakers и observability

## Fixes & Stability
- PR #201: RAM-aware LLM fallback
- PR #202: Стабильный запуск без ImportError из любой директории

## Known Limitations
- Аудио требует ручной настройки Virtual Cable на Windows
- Qt/PyAudio могут требовать установки в dev-окружении
- Нет CI/CD пайплайна (будет в v1.1)

## Thanks
Проект построен как senior-level архитектура с фокусом на локальность и устойчивость.
