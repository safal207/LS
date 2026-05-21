# Rust Meritocracy Core Plan

Related design docs:

- `docs/MULTIMODAL_OPERATOR_PIPELINE_ARCHITECTURE.md`
- `docs/LLM_BACKEND_MODEL_TIERS.md`
- `docs/COOPERATIVE_MERITOCRACY_NETWORK.md`

This document defines the hot-path portion of the meritocracy layer that is worth moving to Rust.

## Why Rust here

The project already has the correct high-level architecture:

- STT for perception
- SmartEar for interpretation
- AgentLoop / ResonanceAgent for decision and prompt assembly
- LLM backends for generation

The hot spot is not the full pipeline. The hot spot is the deterministic selection layer:

- candidate scoring
- backend ranking
- winner selection
- route / fallback decisions
- cheap text cleanup for repeated fragments

Rust is useful here because this path is CPU-bound, deterministic, and runs on every compare / routing decision.

## Non-goals

Do not move the following into Rust:

- STT capture
- SmartEar semantics
- ResonanceAgent policy logic
- LLM provider adapters
- GUI / overlay logic

Those layers are orchestration or network-bound and do not benefit much from a Rust rewrite.

## Proposed crate

Suggested crate name:

- `meritocracy_core`

Suggested packaging:

- Rust library exposed to Python through `PyO3`
- build / distribution through `maturin`

## Data model

### Candidate

```rust
struct Candidate {
    backend: String,
    provider: String,
    model: String,
    text: String,
    ok: bool,
    latency_ms: f64,
    error: Option<String>,
}
```

### QualityScore

```rust
struct QualityScore {
    adequacy: f64,
    relevance: f64,
    thread_relevance: f64,
    coherence: f64,
    hallucination_risk: f64,
    overall: f64,
    notes: Vec<String>,
}
```

### SelectionPolicy

```rust
struct SelectionPolicy {
    min_overall: f64,
    min_relevance: f64,
    min_thread_relevance: f64,
    max_hallucination_risk: f64,
}
```

### SelectionResult

```rust
struct SelectionResult {
    selected_backend: String,
    selected_provider: String,
    selected_model: String,
    ranking: Vec<RankedCandidate>,
    quality_object: QualityScore,
}
```

## Core API

The Rust layer should expose a single entry point:

```rust
fn select_winner(
    question: &str,
    thread_context: Option<&str>,
    candidates: Vec<Candidate>,
    policy: SelectionPolicy,
) -> SelectionResult;
```

Optional helper:

```rust
fn normalize_answer(text: &str) -> String;
```

## Python integration shape

Python should keep orchestration and call Rust only for the hot path:

```text
Question
  -> Gonka / Cloud / Local candidates
  -> Rust meritocracy_core.select_winner(...)
  -> selected backend
  -> optional synthesis
  -> final answer
```

### Python-facing contract

Input from Python:

```python
{
  "question": "...",
  "thread_context": "...",
  "candidates": [
    {
      "backend": "gonka",
      "provider": "gonka",
      "model": "...",
      "text": "...",
      "ok": True,
      "latency_ms": 1234.0,
      "error": None,
    }
  ],
  "policy": {
    "min_overall": 0.35,
    "min_relevance": 0.25,
    "min_thread_relevance": 0.25,
    "max_hallucination_risk": 0.65,
  }
}
```

Output back to Python:

```python
{
  "selected_backend": "cloud",
  "selected_provider": "cloud",
  "selected_model": "qwen/qwen3-32b",
  "ranking": [...],
  "quality_object": {...}
}
```

## Rollout plan

1. Keep the current Python meritocracy router as the reference implementation.
2. Add Rust implementation with identical input/output contracts.
3. Run both paths side-by-side on the same questions.
4. Compare:
   - selection stability
   - latency
   - ranking agreement
   - serialization overhead
5. Switch the Python path to Rust only if the measured gain is real.

## What gains are realistic

Expected wins:

- lower CPU overhead during ranking
- deterministic scoring
- faster compare mode
- easier future scaling to more candidates

Expected non-wins:

- no major LLM latency reduction
- no STT improvement
- no network improvement

## Risks

- over-optimizing a small hot path
- duplicating logic that already exists in Python
- drifting quality heuristics between Rust and Python versions

The safest path is to keep Python as the source of truth until the Rust version is benchmarked.
