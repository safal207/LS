# Mode A Specification (Phase 11)

## Purpose
Mode A is the fast, reactive layer for low-latency responses and simple lookups.
It favors speed over depth and does not perform reasoning.

## Constraints
- No reasoning chains
- No complex explanations
- No context mutation
- Best-effort, low latency

## Interface (v0.2)
```
ModeA.execute(input_data: str, context: dict, system_load: float = 0.0) -> dict
```

## Output
```
{
  "answer": str,
  "mode": "A",
  "source": "fast" | "cache",
  "timestamp": float
}
```

## v0.2 Behavior
- Lightweight heuristics (pattern matching, simple transforms)
- Small in-memory LRU cache (default 128 entries)
- Load-aware: disables non-essential handlers when `system_load >= 0.8`

## Examples
- `echo hello` -> `hello`
- `upper hello` -> `HELLO`
- `pi` -> `3.14159`
- `len hello` -> `5`
- `rev hello` -> `olleh`
- `time` -> `HH:MM:SS`
- `hi` -> `hello`

## Roadmap
- v0.1: skeleton with minimal fast handlers
- v0.2: lightweight heuristics and caching (current)
- v0.3: coordinator integration (Phase 13)
