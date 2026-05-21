# Fast Connect & High-Speed Mode (Operator Runtime)

This guide helps users launch LS with minimal startup friction and maximum response speed.

## What is already optimized

- Persistent HTTP session with keep-alive for LLM requests.
- Streaming response mode for low TTFT (time-to-first-token).
- Native parser chain for streamed frames:
  1. Rust parser,
  2. C++ parser,
  3. Python JSON fallback.

## Recommended startup path (developer mode)

```bash
# 1) Build Rust core (optional but recommended)
cd rust_core
cargo build --release
cp target/release/libghostgpt_core.so ../ghostgpt_core.so
cd ..

# 2) (Optional) Build C++ parser
mkdir -p cpp/build
g++ -O3 -std=c++17 -shared -fPIC cpp/ollama_stream_parser.cpp -o cpp/build/libollama_stream_parser.so

# 3) Run app
python apps/ghostgpt/main.py
```

## Low-latency knobs

- `OLLAMA_NUM_PREDICT`: reduce output length for fast operator-hint mode (e.g. `48`–`96`).

Example:

```bash
export OLLAMA_NUM_PREDICT=64
python apps/ghostgpt/main.py
```

## Proven benchmark snapshot

From latest synthetic benchmark report:

- Streaming TTFT improvement vs non-streaming: ~15.8x faster.
- Parser speedup vs Python JSON parser:
  - Rust: multi-x speedup,
  - C++: measurable speedup.

See details in:
- `docs/operator_runtime_llm_latency_results.md`
- `docs/operator_runtime_llm_latency_review.md`
- `docs/LLM_ACCELERATION_ROADMAP.md`

## What this means for end users

- Faster first hint appearance during live operator workflows.
- Smoother on-screen incremental suggestions.
- Better CPU efficiency on sustained streaming workloads.
