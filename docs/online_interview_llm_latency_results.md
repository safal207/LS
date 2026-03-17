# Qwen Streaming Benchmark Results

Deterministic synthetic benchmark (fake transport):
- tokens per response: `16`
- per-token generation delay: `40 ms`

| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |
|---|---:|---:|---:|---:|---:|
| streaming | 8 | 41.47 | 47.19 | 646.56 | 654.94 |
| non_streaming | 8 | 640.90 | 640.94 | 640.90 | 640.94 |

**TTFT improvement (streaming vs non-streaming): ~15.5x faster**.

Parser micro-benchmark (20k frames):
- Python JSON parser: `58.06 ms`.
- Rust JSON token parser: `10.47 ms` (~5.54x vs Python).
- C++ JSON token parser: `37.23 ms` (~1.56x vs Python).

Interpretation: streaming gives major TTFT gain; native parsers (Rust/C++) reduce CPU overhead in token frame parsing.

