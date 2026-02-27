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
