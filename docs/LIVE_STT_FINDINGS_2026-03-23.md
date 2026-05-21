# Live STT Findings - 2026-03-23

## Current Diagnosis

Local live STT is no longer functionally broken. The end-to-end path works, and `manual-small` is now the default working profile for noisy environments.

The remaining issue is quality under fast speech and background noise, not a dead audio path. The practical ceiling was reached on `faster-whisper base` (`cpu/int8`) in live mode, so the pipeline was shifted to a warmed `small` model with manual phrase capture.

## What Was Confirmed

- The built-in microphone is not the only bottleneck. GPT website transcription on the same laptop performs much better, which points to a stronger cloud stack rather than a dead local input path.
- `manual_mode` proved capture, buffering, and decode were operational.
- `base` was too weak for reliable live noisy STT.
- `small` becomes usable when preloaded to local cache and used in `manual_mode`.

## Current Working Profile

- Script: `scripts/live_ru_stt.py`
- Default profile: `manual-small`
- Model: `small`
- Runtime: `cpu`, `int8`
- Mode: manual phrase capture by `Enter`
- Noise profile: `cafe_mode` enabled
- Model cache: local-only after warmup

## Pipeline Summary

1. Capture audio from `PyAudio` at `16 kHz`, mono, chunked.
2. Calibrate noise floor on startup.
3. Use manual phrase capture in noisy environments.
4. Trim manual recordings with a focused pass, then a wider fallback when needed.
5. For longer recordings, run segmented overlapping decode and merge outputs.
6. Apply light targeted post-corrections from `config/live_stt_corrections.json`.

## What Improved

- `small` loads quickly from cache after warmup.
- Short and medium phrases are now stable enough for practical use.
- Longer phrases now keep more meaning due to segmented retry.
- Repeated tail fragments were reduced by improving segment merge logic.

## Remaining Weaknesses

- Fast speech still causes lexical drift on some words.
- Long phrases can still lose the first or last part, or repeat local fragments.
- Errors now mostly come from ASR quality and segmented merge behavior, not from startup, model loading, or the basic capture path.

## Recommended Next Steps

1. Keep `manual-small` as the default local mode.
2. Continue adding targeted corrections based on real logs.
3. Benchmark this local mode against a remote/server STT path on the same phrase set.
4. If strong real-time noisy STT is required, move to server-side ASR or a larger local model plus stronger preprocessing.
5. See `docs/MULTIMODAL_OPERATOR_PIPELINE_ARCHITECTURE.md` for the STT -> SmartEar -> AgentLoop integration schema.
