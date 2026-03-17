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

## Improvements added in this patch

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

5. **Coverage tests for new stream behavior**
   - Added unit tests for payload override and stream token emission.

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
- Add anti-detection UX mode:
  - concise one-liners,
  - timing randomization,
  - optional keyboard-only overlays.

## Safety and compliance note

If this tool is used in real interviews/negotiations, enforce explicit legal/ethical policy by region and context. Add clear opt-in and usage boundaries inside product UI.
