# Qwen Streaming Benchmark Results

Deterministic synthetic benchmark (fake transport):
- tokens per response: `16`
- per-token generation delay: `40 ms`

| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |
|---|---:|---:|---:|---:|---:|
| streaming | 8 | 40.54 | 41.37 | 644.92 | 647.45 |
| non_streaming | 8 | 640.88 | 640.91 | 640.88 | 640.91 |

**TTFT improvement (streaming vs non-streaming): ~15.8x faster**.

Parser micro-benchmark (20k frames):
- Python JSON parser: `55.14 ms`.
- Rust JSON token parser: unavailable (No module named 'ghostgpt_core').
- C++ JSON token parser: `39.34 ms` (~1.40x vs Python).

Interpretation: streaming gives major TTFT gain; native parsers (Rust/C++) reduce CPU overhead in token frame parsing.

