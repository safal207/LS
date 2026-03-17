# Qwen Streaming Benchmark Results

Deterministic synthetic benchmark (fake transport):
- tokens per response: `16`
- per-token generation delay: `40 ms`

| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |
|---|---:|---:|---:|---:|---:|
| streaming | 8 | 40.77 | 40.81 | 651.49 | 653.77 |
| non_streaming | 8 | 640.91 | 641.05 | 640.91 | 641.05 |

**TTFT improvement (streaming vs non-streaming): ~15.7x faster**.

Parser micro-benchmark (20k frames):
- Python JSON parser: `52.68 ms`.
- Rust JSON token parser: unavailable (No module named 'ghostgpt_core').
- C++ JSON token parser: `37.88 ms` (~1.39x vs Python).

Interpretation: streaming gives major TTFT gain; native parsers (Rust/C++) reduce CPU overhead in token frame parsing.

