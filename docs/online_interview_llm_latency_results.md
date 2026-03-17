# Qwen Streaming Benchmark Results

Deterministic synthetic benchmark (fake transport):
- tokens per response: `16`
- per-token generation delay: `40 ms`

| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |
|---|---:|---:|---:|---:|---:|
| streaming | 8 | 40.39 | 40.48 | 643.33 | 644.85 |
| non_streaming | 8 | 640.90 | 640.94 | 640.90 | 640.94 |

**TTFT improvement (streaming vs non-streaming): ~15.9x faster**.

Parser micro-benchmark:
- Python JSON parser: `53.08 ms` for 20000 frames.
- Rust JSON token parser: `9.17 ms` for 20000 frames (~5.79x vs Python).

Interpretation: streaming drastically reduces *time-to-first-token*, while full completion time remains approximately equal.
