"""
Context Sync - Synchronize results between Mode A and Mode B

v0.1 skeleton: Simple merge strategy
v0.2: Will handle conflicts and cross-checking
"""

from typing import Optional, Dict, Any


class ContextSync:
    """Synchronizes context between modes."""

    def merge(
        self,
        mode_a_result: Optional[Any],
        mode_b_result: Optional[Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge results from A and/or B into context.

        v0.1 strategy:
            - If both results exist: include both, mark source
            - If only A: use A result as "quick"
            - If only B: use B result as "full"

        v0.2 will:
            - Compare results
            - Resolve conflicts using Priority (Codex section 7)
            - Flag discrepancies for learning
        """

        merged = context.copy()

        if mode_a_result is not None:
            merged["mode_a_result"] = mode_a_result
            merged["has_fast_result"] = True

        if mode_b_result is not None:
            merged["mode_b_result"] = mode_b_result
            merged["has_deep_result"] = True

        merged["sync_timestamp"] = __import__("time").time()

        return merged
