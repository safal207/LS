# LLM Backend Model Tiers

This document records the practical strength order of the LLM and STT models currently wired into this repository.

Date of last update: `2026-03-24`

## Scope

This is not a public benchmark leaderboard. It is a project-facing ranking based on:

- what is already integrated into the repository
- what has already been tested in this environment
- current backend wiring in `python/modules/llm/backends/`

The ranking is meant for routing and fallback decisions.

Related design docs:

- `docs/INTERVIEW_STT_SMARTEAR_ARCHITECTURE.md`
- `docs/RUST_MERITOCRACY_CORE_PLAN.md`
- `docs/COOPERATIVE_MERITOCRACY_NETWORK.md`

## LLM Tiers

### Tier 1 — strongest currently verified

1. `qwen/qwen3-235b-a22b-instruct-2507-fp8`
   - Backend: `gonka`
   - Status: verified working in real end-to-end test
   - Role: strongest current primary cloud backend
   - Tradeoff: high latency

2. `openai/gpt-oss-120b`
   - Backend: cloud-class model already used in project experiments
   - Status: strong but not the current default Gonka target
   - Role: escalation / high-quality reasoning mode
   - Tradeoff: can invent specifics if prompt guardrails are weak

### Tier 2 — strong cloud options

3. `qwen/qwen3-32b`
   - Backend: Groq/cloud-class candidate
   - Status: good project fit, good balance of quality and control
   - Role: practical cloud default when available

4. `openai/gpt-oss-20b`
   - Backend: cloud fallback
   - Status: lighter than 120b, still usable
   - Role: cost/speed fallback

### Tier 3 — strong local options

5. `qwen2.5:7b-instruct-q5_k_m`
   - Backend: local Ollama
   - Status: strong local fallback
   - Role: best local reasoning fallback currently configured

6. `qwen2.5:7b`
   - Backend: local Ollama
   - Status: standard local baseline
   - Role: general local path

### Tier 4 — light local fallback

7. `phi4:mini-q5_k_m`
   - Backend: local Ollama
   - Status: lightweight local fallback
   - Role: speed / lower RAM fallback

8. `qwen2.5:1.5b`
   - Backend: local Ollama
   - Status: weakest local LLM currently used in practice
   - Role: emergency local fallback / low-resource mode

## Current practical order

For this repository today, the practical order from strongest to weakest is:

1. `qwen/qwen3-235b-a22b-instruct-2507-fp8`
2. `openai/gpt-oss-120b`
3. `qwen/qwen3-32b`
4. `openai/gpt-oss-20b`
5. `qwen2.5:7b-instruct-q5_k_m`
6. `qwen2.5:7b`
7. `phi4:mini-q5_k_m`
8. `qwen2.5:1.5b`

## Recommended routing

### Production / interview copilot

- Primary: `gonka -> qwen/qwen3-235b-a22b-instruct-2507-fp8`
- Fallback 1: `cloud -> qwen/qwen3-32b` or `openai/gpt-oss-120b`
- Fallback 2: `local -> qwen2.5:7b-instruct-q5_k_m`
- Fallback 3: `local -> qwen2.5:1.5b`

Repository default routing is now:

- `gonka -> cloud -> local`

Meritocracy mode is also available:

- Enable with `LLM_BACKEND=meritocracy`
- Candidate order defaults to `gonka,mimo,cloud,local`
- Selection uses the shared quality object below
- The selected candidate and full ranking are stored in `response.raw["meritocracy"]`
- Future Rust hot path plan: `docs/RUST_MERITOCRACY_CORE_PLAN.md`

MiMo backend is also wired as an OpenAI-compatible provider:

- Enable with `MIMO_ENABLED=true`
- Configure with `MIMO_API_KEY`, `MIMO_BASE_URL`, `MIMO_MODEL`
- It participates in compare mode and meritocracy when configured

### Local-first mode

- Primary: `local -> qwen2.5:7b-instruct-q5_k_m`
- Fallback: `local -> qwen2.5:1.5b`
- Rescue path: `gonka` or `cloud`

## Quality Comparison Object

When comparing multiple backends on the same question, use a shared assessment object:

```json
{
  "adequacy": 0.0,
  "relevance": 0.0,
  "thread_relevance": 0.0,
  "coherence": 0.0,
  "hallucination_risk": 0.0,
  "overall": 0.0,
  "notes": ["balanced"]
}
```

Meaning:

- `adequacy` - does the answer actually answer the question
- `relevance` - lexical/semantic overlap with the question
- `thread_relevance` - alignment with the current conversation thread
- `coherence` - whether the text is structurally complete and readable
- `hallucination_risk` - likelihood of unsupported specifics
- `overall` - single ranking score for comparison

The comparison script is `scripts/test_llm_route.py --compare`.

## Known availability notes

- `qwen/qwen3-32b-fp8` was attempted on Gonka and returned `model_not_found` in this environment.
- `qwen/qwen3-235b-a22b-instruct-2507-fp8` is the strongest Gonka model currently verified working in this project.

## STT note

STT models are not part of the LLM ranking. For speech recognition in this project:

1. `Whisper small`
2. `Whisper base`

`Whisper small` is currently the practical working choice for noisy manual capture.

## Files involved

- `python/modules/llm/backends/base.py`
- `python/modules/llm/backends/local_adapter.py`
- `python/modules/llm/backends/cloud_adapter.py`
- `python/modules/llm/backends/gonka_adapter.py`
- `python/modules/llm/backends/router.py`
- `python/modules/config.py`
