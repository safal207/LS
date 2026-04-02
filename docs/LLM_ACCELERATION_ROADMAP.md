# LLM Acceleration Roadmap (Python → Rust → C++)

Status: **Implemented in this iteration for stream token path + benchmark harness**.

## Goal

Deliver measurable speed evolution for the interview copilot pipeline and publish it in docs/README.

## Phase 1 — Baseline Python (✅ done)

- Pure Python streaming path and JSON parsing baseline.
- Metrics captured:
  - TTFT (stream vs non-stream),
  - parser micro-benchmark (Python).

## Phase 2 — Rust acceleration (✅ done)

- Added `ghostgpt_core.extract_ollama_token(...)` in `rust_core`.
- Integrated Rust fast-path parser in `QwenHandler` with safe fallback.
- Benchmarked parser speedup against Python.

## Phase 3 — C++ acceleration (✅ done)

- Added C++ shared parser (`cpp/ollama_stream_parser.cpp`) and Python loader (`cpp_stream_parser.py`).
- Integrated C++ parser into `QwenHandler` fallback chain:
  1. Rust parser,
  2. C++ parser,
  3. Python JSON fallback.
- Added benchmark support to compile and measure C++ parser speed automatically.

## Phase 4 — Unified comparison report (✅ done)

- Single benchmark script now reports:
  - TTFT stream/non-stream,
  - Python parser timing,
  - Rust parser timing,
  - C++ parser timing.
- Results are published to:
  - `docs/online_interview_llm_latency_results.md`.

## Phase 5 — Public transparency (✅ done)

- README updated with links to roadmap and latest benchmark report.

## Next milestone (planned)

- Real Ollama end-to-end benchmarks on production prompts:
  - p50/p95 TTFT,
  - token throughput,
  - CPU profile by runtime (Python-only vs Rust vs C++).
- Optional: add C++ SIMD JSON (simdjson) parser for higher parser throughput.
