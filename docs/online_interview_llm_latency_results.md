# Qwen Streaming Benchmark Results

Deterministic synthetic benchmark (fake transport):
- tokens per response: `16`
- per-token generation delay: `40 ms`

| mode | runs | avg TTFT (ms) | p95 TTFT (ms) | avg total (ms) | p95 total (ms) |
|---|---:|---:|---:|---:|---:|
| streaming | 8 | 40.40 | 40.44 | 643.44 | 643.89 |
| non_streaming | 8 | 640.89 | 640.92 | 640.89 | 640.92 |

**TTFT improvement (streaming vs non-streaming): ~15.9x faster**.

Interpretation: streaming drastically reduces *time-to-first-token*, while full completion time remains approximately equal.

