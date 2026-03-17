# Qwen Streaming Benchmark Results

Deterministic synthetic benchmark (fake transport):
- tokens per response: `16`
- per-token generation delay: `40 ms`

| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |
|---|---:|---:|---:|---:|---:|
| streaming | 8 | 40.49 | 41.16 | 644.26 | 647.07 |
| non_streaming | 8 | 640.88 | 641.03 | 640.88 | 641.03 |

**TTFT improvement (streaming vs non-streaming): ~15.8x faster**.

Parser micro-benchmark (20k frames):
- Python JSON parser: `57.23 ms`.
- Rust JSON token parser: `9.97 ms` (~5.74x vs Python).
- C++ JSON token parser: `37.14 ms` (~1.54x vs Python).

Interpretation: streaming gives major TTFT gain; native parsers (Rust/C++) reduce CPU overhead in token frame parsing.

