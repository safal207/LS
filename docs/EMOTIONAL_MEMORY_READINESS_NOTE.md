# Phase 2.4 Readiness Note — Emotional Memory & Long-term Bonding

_Date: 2026-04-12_

---

## Status: READY FOR REVIEW

All acceptance criteria from the Phase 2.4 spec have been implemented and
smoke-tested.

---

## What Was Delivered

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `EmotionalMemoryEntry` model + JSONL persistence | ✅ Done |
| 2 | `RelationalSelf.emotional_summary` (additive field) | ✅ Done |
| 3 | `ask_self` returns emotional layer + emotional causal nodes | ✅ Done |
| 4 | MCP resource `self/emotional-memory` | ✅ Done |
| 5 | MCP resource `self/emotional-arc` | ✅ Done |
| 6 | MCP tool `get_emotional_insight` | ✅ Done |
| 7 | Deterministic bond update logic (max ±0.08 step) | ✅ Done |
| 8 | Retention caps (1 000 entries/arc points) + malformed-row robustness | ✅ Done |
| 9 | All existing MCP consumers remain backward-compatible | ✅ Verified |

---

## New Files

| File | Role |
|------|------|
| `python/modules/cognition/emotional_memory.py` | `EmotionalBondingEngine` — deterministic tone/bond/decay/aggregate |
| `python/tests/test_emotional_memory.py` | T-1 model · T-2 store · T-3 builder · T-6 determinism · T-7 safety |
| `python/tests/test_emotional_self_ask.py` | T-4 ask_self · T-5 MCP resources+tool |
| `docs/EMOTIONAL_MEMORY_ARCHITECTURE.md` | Full architecture reference |
| `docs/EMOTIONAL_MEMORY_READINESS_NOTE.md` | This file |

---

## Modified Files

| File | Change |
|------|--------|
| `python/modules/graph/models.py` | Added `EmotionalMemoryEntry`; extended `RelationalSelf` with `emotional_summary` |
| `python/modules/graph/memory_store.py` | Added emotional memory persistence methods + preserved `emotional_summary` across cognitive updates; rollback path writes emotional memory |
| `python/modules/cognition/relational_self.py` | Builder refreshes `emotional_summary` after cycle updates |
| `python/modules/cognition/emotional_memory.py` | Negation-aware `_feedback_matches()` with EN+RU feedback lexicons (`_*_FEEDBACK_ALL`) and RU negation words (не/нет/никогда/ни); `compute_temporal_decay(now=)` parameter for deterministic testing |
| `python/ls/agent_shell/cognitive_state.py` | Added `get_emotional_memory`, `get_emotional_arc`, `get_emotional_insight`; extended `ask_self` with bilingual (EN+RU) emotional intent detection (negation-agnostic topic routing), discourse-marker stripping in `_normalise_for_topic()`, `_detect_language()` for response language selection, `_TONE_NAMES_RU` for localized tone labels; bilingual answers in `ask_self()` and `get_emotional_insight()`; `bond_shift` nodes carry `confidence` |
| `python/ls/agent_shell/mcp_resources.py` | Added `self/emotional-memory`, `self/emotional-arc` resources |
| `python/ls/agent_shell/mcp_tools.py` | Added `get_emotional_insight` tool |
| `python/modules/council/council_engine.py` | `_self_preservation` includes `emotional_context` snapshot (informational only) |
| `python/modules/council/cycle_runner.py` | `run()` writes emotional memory at end of each council cycle |
| `python/modules/graph/care_cycle.py` | Triggers `update_emotional_memory_from_cycle` on meaningful interactions |

---

## Framing Note

This system **does not** claim that LS experiences emotions. It infers and
accumulates emotional signals from observable, measurable system behaviour:

- User feedback polarity
- Resonance / alignment / coherence scores
- Omni signal (fatigue, etc.)
- Rollback / contradiction / policy events

All outputs are tagged with `trigger_source` and `confidence`. The word
"inferred" deliberately precedes all emotional state claims in answers and
summaries. No output asserts subjective experience.

---

## Backward Compatibility

- `emotional_summary` defaults to `{}` on all pre-existing `RelationalSelf`
  records — `from_dict` handles missing field gracefully.
- All 18 existing MCP resources continue to function unchanged.
- All 12 existing MCP tools continue to function unchanged.
- `ask_self` response gains two new keys (`emotional_layer`, extended
  `causal_trace`) but all prior keys remain present.
- `_self_preservation` output gains `emotional_context` but `blocked`,
  `reason`, `coherence_score`, `threshold`, and `constitution` are unchanged.

---

## Known Scope Boundaries (Not in MVP)

- No LLM-generated affective model
- No attachment modeling
- No shared emotional memory across multiple users
- No multimodal fusion beyond simple heuristics
- Emotional state cannot override constitution / policy gates (by design)

---

## Test Coverage Summary

```
test_emotional_memory.py
  TestEmotionalMemoryEntryDefaults          — 6 tests
  TestEmotionalMemoryEntryClamping          — 5 tests
  TestEmotionalMemoryEntryValidation        — 4 tests
  TestEmotionalMemoryEntrySerialisation     — 3 tests
  TestRelationalSelfEmotionalSummaryField   — 4 tests
  TestEmotionalBondingEngineToneInference   — 11 tests
  TestBilingualFeedbackLexicons             — 8 tests  ← NEW (fix-4)
  TestEmotionalBondingEngineBondUpdate      — 5 tests
  TestEmotionalBondingEngineDecay           — 5 tests
  TestEmotionalBondingEngineAggregate       — 6 tests
  TestStoreEmotionalMemory                  — 5 tests
  TestStoreEmotionalArc                     — 4 tests
  TestStoreEmotionalSummaryInSelf           — 2 tests
  TestRelationalSelfBuilderEmotionalSummary — 2 tests
  TestDeterminism                           — 3 tests
  TestSafetyBoundaries                      — 5 tests

test_emotional_self_ask.py
  TestAskSelfEmotionalLayer              — 8 tests
  TestMCPResourcesEmotionalMemory        — 4 tests
  TestMCPResourceRegistryEmotional       — 7 tests
  TestMCPToolGetEmotionalInsight         — 6 tests
  TestGetEmotionalInsight                — 5 tests
  TestEmotionalIntentDetection           — 22 tests
  TestBilingualEmotionalPath             — 13 tests  ← extended fix-4/fix-5
  TestDetectLanguage                     — 5 tests   ← NEW (fix-4)
  TestNormaliseForTopic                  — 6 tests   ← NEW (fix-4)
```
