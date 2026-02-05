# Mode A (Fast Mode) Specification

## Overview

Mode A is the lightweight, reactive layer designed for:
- Simple, structured inputs
- Quick responses without reasoning
- Load-aware operation
- Caching of repeated queries

v0.1: Skeleton only
v0.2: Smart heuristics + LRU caching + load-aware behavior
v0.3: Telemetry only (non-adaptive)

---

## v0.2 Features

### 1. Heuristics

#### 1.1 String Commands (O(n))
All commands are PREFIX-based, executed instantly:

```
"len hello" -> 5
"rev hello" -> olleh
"trim  hello  " -> hello
"upper hello" -> HELLO
"lower HELLO" -> hello
"words hello world foo" -> 3
```

Implementation:
1. Split input on first space
2. Command = first word
3. Argument = rest
4. Execute and return

#### 1.2 Temporal Lookup (O(1))

```
"time" -> "14:32"
"date" -> "2024-01-15"
"day" -> "Monday"
"now" -> "2024-01-15 14:32:05"
```

Implementation: Python built-in datetime.

#### 1.3 Mini-NLU (Pattern Matching)

Greeting mapping:
```
"hi", "hey", "hello", "greetings" -> "Hello! How can I help?"
```

Gratitude mapping:
```
"thanks", "thank you", "thx" -> "You're welcome!"
```

#### 1.4 Math (Simple Arithmetic)

Only + - * /, no parentheses, left-to-right evaluation.

```
"2+2" -> 4
"10 - 3" -> 7
"4*5" -> 20
"20/4" -> 5.0
"2+3*4" -> 20 (left-to-right, no precedence)
```

Restrictions:
- No parentheses
- No functions
- No variables
- Max 3 operations per input

#### 1.5 Echo (Default Fallback)

If no heuristic matches, echo the input.

---

### 2. LRU Caching

Configuration:
- Size: 128 entries
- Strategy: Least Recently Used
- Key: input_data.lower()
- TTL: None (in-process cache only)

Behavior:
1. On input: normalize key
2. If in cache: return cached result (< 1ms)
3. If not in cache: compute via heuristics
4. Add to cache (evict oldest if full)

Important: Cache is process-local, not persisted.

---

### 3. Load-Aware Behavior

When system_load > 0.8 (high load):

Disable:
- rev
- words
- complex math (> 1 operation)

Keep enabled:
- cache lookups
- time/date/day/now
- upper/lower/trim/echo
- greeting/thanks matching

---

### 4. Response Format

All responses are:

```
ModeAResponse:
  result: str
  source: cache | temporal_lookup | string_command | math | mini_nlu | echo
  execution_time_ms: float
  cache_hit: bool
  load_factor: float
```

---

### 5. Guarantees

- No reasoning
- No context mutation
- No hypothesis building
- Linear time complexity (O(n) max)
- Deterministic (except time/date)
- Load-aware (degrades gracefully)
- Always completes (no loops, no recursion)

---

### 6. v0.3 Telemetry (non-adaptive)

v0.3 adds telemetry only. It does not change behavior or heuristic order.
Telemetry is consumed by Retrospective (Phase 12) and does not modify Mode A behavior.

Tracked metrics:
- heuristic usage counts (temporal, math, string, mini_nlu, echo)
- cache hits / misses
- load-shed events (high load)
- input length distribution (min/max/avg + buckets)

API:
- get_stats() -> dict
- reset_stats() -> None

---

### 7. Roadmap

- v0.1: Skeleton
- v0.2: Heuristics + caching + load-aware
- v0.3 (CURRENT): Telemetry only (no adaptive behavior)
- v0.4: Integration with Coordinator

---

## See Also

- docs/BEHAVIOR_CODEX.md ? Formal codex
- Phase 10: Coordinator
- Phase 12: Retrospective
