"""
Test Causal Memory Layer

Smart system for tracking test failures, dependencies, and suggesting fixes.
Learns from historical failures and their resolutions.

Example usage:
```python
from codex.test_causal_memory.layer import TestCausalMemoryLayer

# Create layer
memory = TestCausalMemoryLayer()

# Record a failure
record_id = memory.record_failure(
    test_path="tests/unit/test_example.py",
    test_name="test_example_feature",
    failure_type="assertion",
    error_message="Expected 5 but got 3",
    stack_trace=full_stack_trace,
    module_path="codex/example/module.py",
)

# Get suggestions
suggestions = memory.suggest_fix(record_id)
for suggestion in suggestions:
    print(f"[{suggestion.confidence:.0%}] {suggestion.suggested_action}")
    print(f"   Reason: {suggestion.reasoning}")

# Mark fix as applied
memory.mark_fix_applied(record_id, "Fixed comparison logic", "success")
```
"""

from __future__ import annotations

from .layer import (
    TestCausalMemoryLayer,
    TestFailureRecord,
    ModuleDependency,
    FailurePattern,
    FixSuggestion,
    TestCausalGraph,
    create_test_memory_layer,
)

__all__ = [
    "TestCausalMemoryLayer",
    "TestFailureRecord",
    "ModuleDependency",
    "FailurePattern",
    "FixSuggestion",
    "TestCausalGraph",
    "create_test_memory_layer",
]
