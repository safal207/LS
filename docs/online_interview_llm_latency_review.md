# Online Interview Copilot: LLM Latency & Throughput Architectural Review

## Current strengths

- `QwenHandler` already reuses a single HTTP `Session`, which is the right baseline for lower handshake overhead across repeated LLM calls.
- `LanguageModel` already includes:
  - circuit breaker,
  - RAM-aware model selection,
  - fallback model switching,
  - cancel-event checks.
- Runtime transport layer (`web4_runtime`) already has QoS building blocks: backpressure policy, priority queue, failover transport, and async session control.

## Critical bottlenecks seen for real-time whispering/"тихий подсказчик"

1. **No token streaming to UX path by default**
   - Non-streaming mode waits for full completion before UI receives response.
   - For interview/performance scenarios this hurts TTFT (time-to-first-token).

2. **Synchronous single-shot generation path**
   - Current application path commonly emits one final answer object to UI queue.
   - This limits partial rendering, chunked TTS, and immediate screen prompts.

3. **No explicit low-latency profile contract**
   - Generation options are static and optimized for balanced quality, not minimum latency.
   - No central way to tune short-form "quick hint" responses separately from long-form answers.

4. **No explicit latency SLO telemetry in LLM adapter**
   - There is generic logging, but not structured TTFT / total generation metrics for each request path.

## Improvements delivered

1. **Streaming response mode for Ollama path**
   - Added `generate_with_ollama_stream(...)` with incremental token callback.
   - This allows immediate rendering/forwarding in GUI/TTS pipeline while response is still generating.

2. **Unified payload builder**
   - Added `_build_ollama_payload(...)` to keep streaming and non-streaming parameter parity.

3. **Low-latency generation knob**
   - Added `OLLAMA_NUM_PREDICT` environment override and centralized validation.
   - Enables short response profiles (e.g., 32–96 tokens) for "live hint" mode.

4. **Keep-alive session intent made explicit**
   - Session now explicitly keeps connection alive via headers.

5. **Rust-accelerated stream frame parsing**
   - Added `ghostgpt_core.extract_ollama_token(...)` and integrated it as fast path in Python streaming loop.

6. **C++ stream parser fallback**
   - Added `cpp/ollama_stream_parser.cpp` + Python loader and integrated fallback chain: Rust -> C++ -> Python JSON.

7. **Coverage tests for new stream behavior**
   - Added unit tests for payload override, stream token emission, and native fast-path fallback behavior.

## Test evidence: with feature vs without feature

See measured benchmark report:
- `docs/online_interview_llm_latency_results.md`

Method:
- deterministic synthetic transport benchmark,
- same token count and per-token delay,
- compare `stream=True` vs `stream=False` for the same handler.

Result summary (current run):
> Note: latest measured values are published in `docs/online_interview_llm_latency_results.md` and may differ by environment/build cache.
- **TTFT improved significantly** with streaming (see latest benchmark report for exact value),
- full completion time remained roughly equal,
- **Rust parser micro-benchmark gives multi-x speedup** vs Python JSON parse (see latest report),
- **C++ parser micro-benchmark gives measurable speedup** vs Python JSON parse (see latest report),
- this is exactly what we want for interview whisper mode: first useful hint appears much earlier with lower CPU overhead in stream parsing.

## Recommended next architecture step (high impact)

- Introduce a dedicated **Realtime Hint Pipeline**:
  1. STT partial transcript window (rolling 1.5–3s).
  2. Prompt compressor (strict token budget).
  3. LLM streaming with max short output.
  4. Immediate UI/TTS incremental dispatch.
  5. Background "full reasoning" pass separately (optional).

This dual-lane architecture gives you both speed and quality:
- lane A = ultra-fast hints,
- lane B = deeper synthesized answer.

See also: `docs/INTERVIEW_STT_SMARTEAR_ARCHITECTURE.md` for the end-to-end `Mic -> STT -> SmartEar -> AgentLoop -> LLM` contract and backend placement.

## Competitive target SLOs (practical)

- TTFT (local Ollama): `< 350ms` for short hints on warmed model.
- End-to-end hint (partial STT -> first visible token): `< 700ms`.
- End-to-end hint (partial STT -> first TTS chunk): `< 900ms`.
- p95 no-drop transport queue under interview load.

## Product-level suggestions for "внеконкуренции"

- Add interview-mode presets:
  - `stealth_fast` (max speed, short hints, low verbosity)
  - `coach_balanced`
  - `deep_answer`
- Add confidence gate before speaking hints (avoid noisy/unsafe suggestions).
- Add low-distraction UX mode:
  - concise one-liners,
  - compact overlays,
  - user-controlled verbosity and pacing.

## Safety and compliance note

If this tool is used in real interviews/negotiations, enforce explicit legal/ethical policy by region and context. Add clear opt-in and usage boundaries inside product UI.


## Follow-up runtime improvements

- Added early exit for Ollama `done` stream frame to avoid unnecessary parser-chain work.
- Added structured TTFT telemetry log (`llm.ttft_ms=... path=stream`).
- Added streaming-first queue events in `LanguageModel.run`: token events, punctuation-based `tts_chunk` events, and final response event.
- Added whisper-mode message compressor helper for fast-hint mode (`WHISPER_MODE=1`).
