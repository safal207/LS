# Changelog

## [1.2.1] - 2026-03-05

### Notable
- Первый публичный релиз на PyPI. Прыжок версии с 0.1.0 → 1.2.1 — проект начинался как внутренний прототип.

### Added
- Двуязычный README (English / Русский)
- Профессиональный CONTRIBUTING.md
- Покрытие perception-модуля ≥94%
- PyPI-ready конфигурация с optional-dependencies (vision, audio, ml, full)
- Sleep & Homeostasis: автоматический режим сна (1800 с) для консолидации памяти
- Immune & Safety: адаптивная блокировка инъекций без вызова LLM
- Qwen3.5 Small Series ready + динамическая модельная политика

### Fixed / Improved
- Refactoring MetabolismEngine → Metabolism с автоматической миграцией старых снапшотов

## [1.0] - 2026-02-27
### Key Features
- Полностью локальный запуск (Ollama + Qwen2.5-7B / Phi-4-mini fallback)
- RAM-aware модельный выбор
- Interview Copilot (Ghost Mode)
- Temporal/causal memory + AgentLoop
- Resonance eval harness
