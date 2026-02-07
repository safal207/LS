# Bug Scan Report - 2025-02-07

## Summary
Total bugs found: 299

## CRITICAL Bugs (Need Fix)

### 1. Dataclass Field Order Issues
**Files affected:**
- `codex/cognitive/loop.py` (lines 105, 106)
- `codex/cognitive/self_model/affect.py` (lines 11, 12)
- `codex/cognitive/self_model/model.py` (lines 12, 13, 14)

**Problem:** Non-default fields after default fields in dataclass
**Example:**
```python
@dataclass
class Example:
    field1: str = "default"  # default
    field2: str             # non-default - ERROR!
```

**Fix:** Reorder fields - all non-default fields must come before fields with defaults

### 2. Syntax Errors
**File:** `python/modules/audio/audio_module.py`
**Status:** Has syntax errors preventing import

## HIGH Severity

### Unreachable Code
**Files to check:**
- Multiple files may have code after return statements

## MEDIUM Severity

### Common Issues Found:
1. **Bare except clauses** - Catching all exceptions including KeyboardInterrupt
2. **Index access [0]** - Potential IndexError on empty lists
3. **Division operations** - Potential division by zero
4. **Hardcoded paths** - Not using pathlib

## Recommendations

1. Fix all CRITICAL dataclass field order issues first
2. Fix syntax errors in audio_module.py
3. Review all MEDIUM severity warnings
4. Add proper error handling for index access and division

## Files Needing Immediate Attention

1. `codex/cognitive/loop.py` - Fix dataclass field order
2. `codex/cognitive/self_model/affect.py` - Fix dataclass field order
3. `codex/cognitive/self_model/model.py` - Fix dataclass field order
4. `python/modules/audio/audio_module.py` - Fix syntax errors

## Next Steps

Run individual fixes for each CRITICAL bug, then re-run tests.
