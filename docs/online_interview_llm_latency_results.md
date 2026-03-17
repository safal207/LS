# Qwen Streaming Benchmark Results

Deterministic synthetic benchmark (fake transport):
- tokens per response: `16`
- per-token generation delay: `40 ms`

| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |
|---|---:|---:|---:|---:|---:|
| streaming | 8 | 59.95 | 87.58 | 797.38 | 892.61 |
| non_streaming | 8 | 646.98 | 655.42 | 646.98 | 655.42 |

**TTFT improvement (streaming vs non-streaming): ~10.8x faster**.

Parser micro-benchmark (20k frames):
- Python JSON parser: `264.02 ms`.
- Rust JSON token parser: unavailable (No module named 'ghostgpt_core').
- C++ JSON token parser: `49.10 ms` (~5.38x vs Python).

Interpretation: streaming gives major TTFT gain; native parsers (Rust/C++) reduce CPU overhead in token frame parsing.

