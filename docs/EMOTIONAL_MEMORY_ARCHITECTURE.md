# Emotional Memory & Long-term Bonding — Architecture

_Phase 2.4 · LS Cognitive Architecture_

---

## Overview

Phase 2.4 adds an **inferred emotional memory layer** to LS. The system tracks
emotional tone, bond strength, and relational arc over time using deterministic,
rule-based heuristics — not probabilistic models or LLM-generated affect.

> **Key principle:** All outputs represent *inferred* signals derived from
> observable system behaviour. The system does not claim real subjective
> experience. Preferred terms: `emotional_tone`, `bond_strength`,
> `inferred_emotional_state`, `emotional_arc`.

Constitution and policy gates remain supreme. Emotional context is advisory
and informational only — it never bypasses governance or auto-applies actions.

---

## Component Map

```
Care Cycle / Council / ask_self
        │  (signals: resonance, alignment, coherence,
        │   omni, feedback, rollback, contradiction)
        ▼
EmotionalBondingEngine              python/modules/cognition/emotional_memory.py
  ├── infer_tone()       → tone, intensity, valence, confidence
  ├── update_bond_strength()         (max ±0.08 per step)
  ├── compute_temporal_decay()       (exponential, floor 0.05)
  └── aggregate_emotional_summary()  (weighted by decay × confidence)
        │
        ▼
MemoryGraphStore                    python/modules/graph/memory_store.py
  ├── store_emotional_memory_entry()    → relational_self_emotional_memory.jsonl
  ├── get_emotional_memory(limit)
  ├── update_emotional_memory_from_cycle()
  ├── _append_emotional_arc_point()     → relational_self_emotional_arc.jsonl
  ├── get_emotional_arc(limit)
  └── _update_emotional_summary_in_self()  (additive write to relational_self.json)
        │
        ▼
RelationalSelf.emotional_summary    python/modules/graph/models.py
  (additive field — never breaks existing consumers)
        │
        ▼
CognitiveStateBridge                python/ls/agent_shell/cognitive_state.py
  ├── get_emotional_memory()
  ├── get_emotional_arc()
  ├── get_emotional_insight()
  └── ask_self()  ← extended with emotional layer + causal_trace nodes
        │
        ▼
MCP Surface
  Resources:  self/emotional-memory   self/emotional-arc
  Tool:       get_emotional_insight
```

---

## Data Models

### `EmotionalMemoryEntry`

```python
@dataclass
class EmotionalMemoryEntry:
    entry_id:          str           # UUID
    timestamp:         str           # ISO-8601 UTC
    schema_version:    str           # "1.0"
    emotional_tone:    str           # see valid tones below
    emotional_intensity: float       # 0.0..1.0
    valence:           str           # negative | neutral | positive | mixed
    confidence:        float         # 0.0..1.0
    bond_strength:     float         # 0.0..1.0
    temporal_decay:    float         # 0.0..1.0 (recomputed on read)
    trigger_source:    str           # see valid sources below
    relational_context: list[str]    # unit_id / cycle_id refs
    summary:           str           # human-readable description
    metadata:          dict          # resonance/alignment/coherence scores
```

**Valid tones:** `warm` · `calm` · `reflective` · `joyful` · `anxious` ·
`frustrated` · `tense` · `supportive` · `uncertain` · `neutral`

**Valid trigger sources:** `user_feedback` · `omni_insight` · `care_cycle` ·
`council` · `ask_self` · `system_inference`

### `RelationalSelf.emotional_summary`

Additive field added to the existing `RelationalSelf` dataclass:

```json
{
  "dominant_tone": "warm",
  "dominant_valence": "positive",
  "bond_strength": 0.67,
  "bond_trend": "warming",
  "last_emotional_update_at": "2026-04-12T14:30:00+00:00",
  "recent_entry_count": 12,
  "confidence": 0.74,
  "notable_moments": [
    {
      "timestamp": "2026-04-10T09:12:00+00:00",
      "tone": "reflective",
      "summary": "Deep reflective exchange increased relational trust signal."
    }
  ]
}
```

---

## Tone Inference Rules (Deterministic Priority Order)

| Priority | Condition | Tone | Valence | Confidence |
|----------|-----------|------|---------|------------|
| 1 | Explicit positive feedback + high R/A | `warm` | positive | 0.87 |
| 1 | Explicit positive feedback | `joyful` | positive | 0.82 |
| 1 | Distress / concern feedback | `supportive` | mixed | 0.80 |
| 1 | Frustration / anger feedback | `frustrated` | negative | 0.80 |
| 2 | Omni fatigue signal + coherence ≥ 0.6 | `supportive` | mixed | 0.70 |
| 2 | Omni fatigue signal + coherence < 0.6 | `calm` | neutral | 0.65 |
| 3 | Rollback present + coherence ≥ 0.5 | `supportive` | mixed | 0.65 |
| 3 | Rollback present + coherence < 0.5 | `uncertain` | mixed | 0.60 |
| 3 | Contradiction spike | `tense` | negative | 0.62 |
| 3 | Coherence > 0 and < 0.3 | `tense` | negative | 0.58 |
| 3 | Policy blocked | `uncertain` | mixed | 0.62 |
| 3 | Reflective context | `reflective` | neutral | 0.65 |
| 3 | R ≥ 0.75 ∧ A ≥ 0.75 ∧ C ≥ 0.7 | `warm` | positive | 0.72 |
| 3 | Coherence ≥ 0.65 | `calm` | neutral | 0.68 |
| — | Default | `neutral` | neutral | 0.50 |

R = resonance_score, A = alignment_score, C = coherence_score

---

## Bond Strength Semantics (FR-4)

Bond strength (0.0..1.0) measures **relational stability**, not momentary
warmth. Key properties:

- Max ±0.08 step per update (prevents single-event dominance)
- Repair after rupture (`rollback_present=True` + coherence ≥ 0.5) is
  **net-positive** — successful resolution strengthens the bond
- Sustained contradiction (`contradiction_spike=True`) is net-negative
- Result always clamped to [0.0, 1.0]

Formula:

```
base = 0.4·resonance + 0.4·alignment + 0.2·coherence − 0.5
delta = clamp(base + tone_boost + repair_boost + depth_boost, −0.08, +0.08)
new_bond = clamp(current + delta, 0.0, 1.0)
```

---

## Temporal Decay (FR-5)

Each entry has a `temporal_decay` weight recomputed on every read:

```
weight = 0.5 ^ (age_hours / 72.0)    # 72h = default half-life
weight = max(0.05, min(1.0, weight))  # floor at 0.05 — entries never vanish
```

Aggregate summaries use `temporal_decay × confidence` as weights so recent,
high-confidence entries dominate dominant_tone and dominant_valence.

---

## Storage Files

| File | Format | Retention cap |
|------|--------|--------------|
| `relational_self_emotional_memory.jsonl` | JSONL, one entry per line | 1 000 rows |
| `relational_self_emotional_arc.jsonl` | JSONL, one arc point per line | 1 000 rows |
| `relational_self.json` | JSON | single snapshot (additive `emotional_summary` field) |

All writes are atomic (temp-file + `os.replace`). Malformed rows are skipped
on read, never raising exceptions.

---

## MCP Surface

### Resources (read-only)

#### `self/emotional-memory`
```json
{
  "resource": "self/emotional-memory",
  "entries": [...],
  "emotional_summary": { ... },
  "limit": 50,
  "last_updated": "..."
}
```

#### `self/emotional-arc`
```json
{
  "resource": "self/emotional-arc",
  "arc": [{ "timestamp": "...", "bond_strength": 0.6, "dominant_tone": "warm", ... }],
  "bond_trend": "warming",
  "limit": 100,
  "last_updated": "..."
}
```

### Tool

#### `get_emotional_insight(question, limit=10)`
```json
{
  "resource": "self/emotional-insight",
  "question": "...",
  "answer": "...",
  "dominant_tone": "warm",
  "bond_strength": 0.67,
  "bond_trend": "warming",
  "supporting_entries": [...],
  "causal_trace": [
    { "type": "emotional_event", ... },
    { "type": "bond_shift", ... },
    { "type": "emotional_summary_state", ... }
  ],
  "last_updated": "..."
}
```

### Extended `ask_self`

`ask_self` now includes:

- `emotional_layer` key: full `emotional_summary` dict
- Emotional nodes in `causal_trace`: `emotional_event`, `bond_shift`,
  `emotional_summary_state`
- For emotionally-framed questions: answer includes tone/bond description

---

## Integration Points

### Care Cycle (`CareCycleRunner`)

After a successful `keep`/`promote` cycle with resonance > threshold:

1. Stores `ResonanceKnowledgeUnit`
2. Calls `update_self_from_cycle()` (existing)
3. **New:** calls `update_emotional_memory_from_cycle()` with resonance +
   alignment scores from the cycle

### Council (`RelationalCouncilEngine`)

`_self_preservation` now includes an `emotional_context` field in its output:

```json
{
  "emotional_context": {
    "dominant_tone": "warm",
    "bond_strength": 0.67,
    "bond_trend": "warming",
    "confidence": 0.74,
    "constitution_override": false
  }
}
```

`constitution_override` is always `false`. Emotional state never gates or
bypasses the constitution check.

### `RelationalSelfBuilder`

`update()` now refreshes `emotional_summary` from the store after writing the
cognitive snapshot, ensuring callers always see a consistent picture.

---

## Architectural Constraints

| Constraint | Implementation |
|------------|---------------|
| Constitution is always primary | `emotional_context.constitution_override = False`; `blocked` flag is never toggled by emotional state |
| Emotional memory is separate from factual memory | Stored in separate JSONL files; never merged with `resonance_units.jsonl` |
| Deterministic MVP | All rules are `if/elif` chains; no randomness; same inputs → same outputs |
| Additive backward compat | `emotional_summary` defaults to `{}` on all existing `RelationalSelf` records; all new MCP keys are additive |
| Retention caps | 1 000 entries max for both memory and arc |

---

## Explainability (NFR-4)

Every `EmotionalMemoryEntry` carries:
- `trigger_source` — what generated the entry
- `confidence` — how reliable the inference is
- `metadata` — the raw signal values (resonance, alignment, coherence)
- `summary` — a human-readable explanation of the inference

Every `get_emotional_insight` response carries a full `causal_trace` linking
emotional events to bond shifts to the current summary state.
