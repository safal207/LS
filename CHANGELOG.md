# Changelog

All notable changes to this project will be documented in this file.

## [1.2.1] - 2026-03-05

### Added
- Bilingual README (English / Russian) for global accessibility.
- Professional `CONTRIBUTING.md` guidelines for community participation.
- Expanded test suite for the perception module (94%+ coverage), covering concurrency and zero-copy buffers.
- PyPI-ready `pyproject.toml` with modular optional dependencies (`vision`, `audio`, `ml`, `full`).
- **Sleep & Homeostasis**: Autonomous sleep mode for memory consolidation and cognitive recovery.
- **Immune & Safety**: Adaptive injection protection and safety gates.
- Support for Qwen3.5 Small Series with dynamic model selection policy.

### Changed
- Improved `Metabolism` engine with robust state migration for cognitive snapshots.
- Optimized Rust-accelerated vision pipeline with zero-copy memory management.

### Fixed
- Resolved race conditions in the vision subsystem during rapid state transitions.
- Fixed metadata eviction leaks in the frame buffer.
- Corrected greedy redaction conflicts in multi-PII scenarios.

## [1.0.0] - 2026-02-27
### Initial Release Features
- Full local execution (Ollama + Qwen/Phi).
- RAM-aware model selection.
- Interview Copilot (Ghost Mode).
- Temporal/causal memory integration.
- AgentLoop state machine (Idle/Listening/Thinking/Responding).
