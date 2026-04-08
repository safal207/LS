# Multimodal STT / SmartEar / AgentLoop Architecture

This document defines how live speech recognition connects to multimodal operator-context interpretation and answer generation in this repository.

Related design docs:

- `docs/LLM_BACKEND_MODEL_TIERS.md`
- `docs/RUST_MERITOCRACY_CORE_PLAN.md`
- `docs/COOPERATIVE_MERITOCRACY_NETWORK.md`

## Core Principle

- `STT = perception`
- `SmartEar = interpretation`
- `AgentLoop = decision / action`

Do not move operator semantics into the STT layer. Keep STT backend-agnostic and keep response policy above it.

## High-Level Flow

```text
[Mic / AudioIngestion]
        |
        v
[STT Adapter]
        |
        +-- local Whisper
        |      - scripts/live_ru_stt.py
        |      - python/modules/stt/stt_module.py
        |
        +-- cloud ASR fallback
        |
        v
OperatorUtterance
        |
        v
[SmartEar]
        |
        +-- cleanup / corrections
        +-- phonetic normalization
        +-- question detection
        +-- intent
        +-- why
        +-- strategy
        +-- interaction_profile
        +-- anchor_context
        |
        v
[AgentLoop / ResonanceAgent]
        |
        +-- memory / context injection
        +-- prompt assembly
        +-- local or cloud LLM selection
        +-- answer generation
        +-- resonance scoring
        |
        v
[Final answer]
        |
        v
[Feedback loop]
        |
        +-- correction dictionary
        +-- interaction profile learning
        +-- strategy tuning
```

## Local / Cloud Placement

Local/cloud is a backend choice at two boundaries only:

1. `speech -> text`
   - local Whisper
   - cloud ASR

2. `text -> answer`
   - local LLM
   - cloud LLM

`SmartEar` stays backend-agnostic.

## File-Level Map

```text
scripts/live_ru_stt.py
    experimental live STT stand
    manual capture, noisy-room diagnostics, phrase trimming, local model warmup

python/modules/stt/stt_module.py
    reusable STT interface
    model load, transcription, question emission

python/modules/stt/adapters.py
    STT adapter contract
    local / cloud adapters
    fallback routing by confidence

python/modules/stt/factory.py
    backend selection helper
    profile-driven local / fallback / cloud wiring

python/modules/stt/smart_ear.py
    semantic normalization layer
    filter / hypothesis / selection / intent / why / strategy

python/modules/agent/resonance_agent.py
    answer orchestration
    pipeline enrichment, prompt construction, resonance scoring

python/modules/agent/loop.py
    runtime shell
    memory, reflection, prompt injection, backend call
```

## Call Sequence

```text
1. SpeechToText.transcribe_audio()
2. SpeechToText.process_result()
3. SmartEar._process()
4. FilterStage.process()
5. HypothesisStage.process()
6. SelectionStage.process()
7. IntentStage.process()
8. WhyStage.process()
9. WhyStrategyStage.process()
10. AgentLoop._process_item()
11. ResonanceAgent._run_pipeline()
12. BodyAwareCopilot._build()
13. LLM backend call
14. Final answer
15. Feedback updates corrections / profile / strategy
```

## OperatorUtterance Contract

Use one shared structure across STT and SmartEar:

```python
OperatorUtterance(
    type="question",
    text="Summarize the current operator request.",
    confidence=0.91,
    source="local_stt",
    words=[...],
    clean_text="What are your strengths?",
    intent="task_clarification",
    why="support_decision",
    why_strategy={...},
    operator_profile={...},
    anchor_context=[...],
)
```

Minimum rule:

- STT returns `text`, `confidence`, `words`, `source`.
- SmartEar enriches the same object.
- AgentLoop consumes only the enriched object.

## Runtime Modes

### 1. All-local

```text
Mic -> Local STT -> SmartEar -> AgentLoop -> Local LLM -> Answer
```

Good for:
- offline mode
- privacy mode
- debugging
- deterministic local testing

Tradeoff:
- weaker noisy-room STT
- weaker reasoning on limited hardware

### 2. Hybrid

```text
Mic -> Local capture / light VAD -> Cloud ASR -> SmartEar -> AgentLoop -> Cloud LLM -> Answer
```

Good for:
- live operator runtime
- strongest STT quality
- stronger answer quality
- product MVP

Tradeoff:
- network dependency
- cost
- privacy policy required

### 3. Mixed fallback

```text
Mic -> Local capture -> Local STT
                    \-> Cloud STT fallback
SmartEar -> AgentLoop -> Local or Cloud LLM
```

Good for:
- graceful degradation
- offline-first UX with cloud rescue path

## Current Repository Status

The current working local STT profile is `manual-small` in `scripts/live_ru_stt.py`. It is useful for noisy rooms and manual phrase capture, but it is still a perception layer only. Operator logic should stay in `SmartEar`, `ResonanceAgent`, and `AgentLoop`.

Current LLM backend tiers and routing guidance are documented in `docs/LLM_BACKEND_MODEL_TIERS.md`.
The future Rust hot path for meritocracy selection is documented in `docs/RUST_MERITOCRACY_CORE_PLAN.md`.

## Recommended Next Implementation Step

1. Introduce `OperatorUtterance` as a shared contract.
2. Add `LocalSTTAdapter` and `CloudSTTAdapter`.
3. Add a factory that wires adapters from profile/config.
4. Make `SmartEar` consume and enrich the shared contract.
5. Keep `AgentLoop` as the runtime shell and answer router.
6. Add explicit `local -> cloud` fallback when STT confidence is low.
