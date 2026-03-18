"""
Test Causal Memory Layer

Smart system for tracking test failures, dependencies, and suggesting fixes.
Learns from historical failures and their resolutions.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class TestFailureRecord:
    """Record of a single test failure."""
    record_id: str
    test_path: str
    test_name: str
    failure_type: str  # "error", "assertion", "timeout", "import"
    error_message: str
    stack_trace: str | None = None
    module_path: str | None = None
    dependencies_affected: List[str] = field(default_factory=list)
    suggested_fix: str | None = None
    fix_applied: bool = False
    fix_result: str | None = None  # "success", "failed", "partial"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModuleDependency:
    """Dependency relationship between modules."""
    source_module: str
    target_module: str
    dependency_type: str  # "import", "inherits", "calls", "configures"
    strength: float = 1.0  # 0.0 to 1.0


@dataclass(frozen=True)
class FailurePattern:
    """Pattern of recurring failures."""
    pattern_id: str
    signature: str  # Hash of failure characteristics
    frequency: int
    first_occurrence: str
    last_occurrence: str
    affected_tests: List[str]
    root_causes: List[str]
    successful_fixes: List[str]
    success_rate: float


@dataclass(frozen=True)
class FixSuggestion:
    """Suggested fix for a failure."""
    suggestion_id: str
    failure_record_id: str
    confidence: float  # 0.0 to 1.0
    suggested_action: str
    affected_files: List[str]
    reasoning: str
    source: str  # "pattern_match", "dependency_analysis", "manual"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TestCausalGraph:
    """Graph of test dependencies and failure propagation."""

    def __init__(self) -> None:
        self._nodes: Set[str] = set()
        self._edges: Dict[str, Set[str]] = {}  # node -> set of dependencies
        self._failures: Dict[str, List[str]] = {}  # node -> list of failure record_ids

    def add_node(self, node: str) -> None:
        """Add a test or module to the graph."""
        self._nodes.add(node)
        if node not in self._edges:
            self._edges[node] = set()

    def add_dependency(
        self, source: str, target: str, dependency_type: str = "import", strength: float = 1.0
    ) -> None:
        """Add a dependency edge."""
        self.add_node(source)
        self.add_node(target)
        self._edges[source].add(target)

    def record_failure(self, node: str, failure_id: str) -> None:
        """Record that a node has a failure."""
        if node not in self._failures:
            self._failures[node] = []
        self._failures[node].append(failure_id)

    def get_affected_by_failure(self, failed_node: str) -> List[str]:
        """Get all nodes that depend on a failed node."""
        affected = set()
        stack = [failed_node]
        visited = set()

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            # Find all nodes that depend on current
            for node, edges in self._edges.items():
                if current in edges and node not in visited:
                    affected.add(node)
                    stack.append(node)

        return list(affected)

    def get_failure_chain(self, start_node: str) -> List[str]:
        """Get the chain of failures from a starting node."""
        chain = []
        stack = [start_node]
        visited = set()

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            if current in self._failures and self._failures[current]:
                chain.append(current)
                # Add dependencies that might have caused this
                for dep in self._edges.get(current, set()):
                    if dep not in visited:
                        stack.append(dep)

        return chain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self._nodes),
            "edges": {k: list(v) for k, v in self._edges.items()},
            "failures": {k: v for k, v in self._failures.items()},
        }


class TestCausalMemoryLayer:
    """
    Smart layer for tracking test failures, dependencies, and suggesting fixes.

    Features:
    - Records test failures with full context
    - Tracks module dependencies
    - Detects recurring failure patterns
    - Suggests fixes based on historical data
    - Learns from successful resolutions
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or Path("test_memory")
        self.store_path.mkdir(parents=True, exist_ok=True)

        self._records: Dict[str, TestFailureRecord] = {}
        self._patterns: Dict[str, FailurePattern] = {}
        self._graph = TestCausalGraph()
        self._fix_suggestions: Dict[str, FixSuggestion] = {}

        self._load_from_disk()

    def _get_record_path(self, record_id: str) -> Path:
        return self.store_path / f"{record_id}.jsonl"

    def _get_pattern_path(self, pattern_id: str) -> Path:
        return self.store_path / f"pattern_{pattern_id}.jsonl"

    def _serialize_record(self, record: TestFailureRecord) -> str:
        return json.dumps({
            "record_id": record.record_id,
            "test_path": record.test_path,
            "test_name": record.test_name,
            "failure_type": record.failure_type,
            "error_message": record.error_message,
            "stack_trace": record.stack_trace,
            "module_path": record.module_path,
            "dependencies_affected": record.dependencies_affected,
            "suggested_fix": record.suggested_fix,
            "fix_applied": record.fix_applied,
            "fix_result": record.fix_result,
            "timestamp": record.timestamp,
            "metadata": record.metadata,
        })

    def _deserialize_record(self, data: str) -> TestFailureRecord:
        obj = json.loads(data)
        return TestFailureRecord(**obj)

    def record_failure(
        self,
        test_path: str,
        test_name: str,
        failure_type: str,
        error_message: str,
        stack_trace: str | None = None,
        module_path: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> str:
        """Record a new test failure."""
        record_id = str(uuid.uuid4())[:8]

        # Extract dependencies from stack trace
        dependencies_affected = self._extract_dependencies(stack_trace)

        record = TestFailureRecord(
            record_id=record_id,
            test_path=test_path,
            test_name=test_name,
            failure_type=failure_type,
            error_message=error_message,
            stack_trace=stack_trace,
            module_path=module_path,
            dependencies_affected=dependencies_affected,
            metadata=metadata or {},
        )

        self._records[record_id] = record
        self._graph.add_node(test_path)
        self._graph.add_node(test_name)

        # Add dependencies to graph
        for dep in dependencies_affected:
            self._graph.add_dependency(test_path, dep)

        # Record in graph
        self._graph.record_failure(test_path, record_id)

        # Save to disk
        with open(self._get_record_path(record_id), "w", encoding="utf-8") as f:
            f.write(self._serialize_record(record))

        # Update patterns
        self._update_patterns(record)

        return record_id

    def _extract_dependencies(self, stack_trace: str | None) -> List[str]:
        """Extract module dependencies from stack trace."""
        if not stack_trace:
            return []

        deps = set()
        # Pattern to capture file path in standard traceback format (handles leading whitespace)
        import re
        pattern = r'\s*File\s+"([^"]+\.(?:py))"'
        matches = re.findall(pattern, stack_trace)
        for path in matches:
            # Convert to module name
            if "codex/" in path:
                # Remove leading ./ or ../ if present
                path = path.lstrip("./")
                module = path.split("codex/")[-1].replace("/", ".").replace(".py", "")
                deps.add(f"codex.{module}")
            elif "python/modules/" in path:
                path = path.lstrip("./")
                module = path.split("python/modules/")[-1].replace("/", ".").replace(".py", "")
                deps.add(f"python.modules.{module}")

        return list(deps)

    def _update_patterns(self, record: TestFailureRecord) -> None:
        """Update failure patterns with new record."""
        # Create signature from error characteristics
        signature = f"{record.failure_type}:{record.error_message[:100]}"

        # Check if pattern exists
        existing = None
        for pattern_id, pattern in self._patterns.items():
            if pattern.signature == signature:
                existing = pattern_id
                break

        if existing:
            # Update existing pattern
            pattern = self._patterns[existing]
            affected = set(pattern.affected_tests)
            affected.add(record.test_path)

            # Update successful fixes if this was fixed
            successful_fixes = list(pattern.successful_fixes)
            if record.fix_applied and record.fix_result == "success":
                if record.suggested_fix:
                    successful_fixes.append(record.suggested_fix)

            # Success rate is 1.0 if we have at least one successful fix, else 0.0
            success_rate = 1.0 if successful_fixes else 0.0

            # Create updated pattern (frozen dataclass, need to recreate)
            self._patterns[existing] = FailurePattern(
                pattern_id=pattern.pattern_id,
                signature=pattern.signature,
                frequency=pattern.frequency + 1,
                first_occurrence=pattern.first_occurrence,
                last_occurrence=record.timestamp,
                affected_tests=list(affected),
                root_causes=pattern.root_causes,
                successful_fixes=successful_fixes,
                success_rate=success_rate,
            )
        else:
            # Create new pattern
            pattern_id = str(uuid.uuid4())[:8]
            self._patterns[pattern_id] = FailurePattern(
                pattern_id=pattern_id,
                signature=signature,
                frequency=1,
                first_occurrence=record.timestamp,
                last_occurrence=record.timestamp,
                affected_tests=[record.test_path],
                root_causes=[],
                successful_fixes=[],
                success_rate=0.0,
            )

    def suggest_fix(self, failure_id: str) -> List[FixSuggestion]:
        """Suggest fixes for a failure based on historical data."""
        if failure_id not in self._records:
            return []

        record = self._records[failure_id]
        suggestions = []

        # 1. Pattern-based suggestions
        signature = f"{record.failure_type}:{record.error_message[:100]}"
        for pattern_id, pattern in self._patterns.items():
            if pattern.signature == signature and pattern.success_rate > 0.3:
                # Found a matching pattern with reasonable success rate
                if pattern.successful_fixes:
                    best_fix = pattern.successful_fixes[0]
                    suggestions.append(FixSuggestion(
                        suggestion_id=str(uuid.uuid4())[:8],
                        failure_record_id=failure_id,
                        confidence=pattern.success_rate,
                        suggested_action=best_fix,
                        affected_files=pattern.affected_tests[:5],
                        reasoning=f"Pattern matched with {pattern.success_rate*100:.0f}% success rate",
                        source="pattern_match",
                    ))

        # 2. Dependency-based suggestions
        affected = self._graph.get_affected_by_failure(record.test_path)
        if affected:
            suggestions.append(FixSuggestion(
                suggestion_id=str(uuid.uuid4())[:8],
                failure_record_id=failure_id,
                confidence=0.5,
                suggested_action=f"Check dependencies: {', '.join(affected[:3])}",
                affected_files=affected[:5],
                reasoning="Failure propagated from dependent modules",
                source="dependency_analysis",
            ))

        # 3. Module-specific suggestions based on error type
        if record.failure_type == "import":
            suggestions.append(FixSuggestion(
                suggestion_id=str(uuid.uuid4())[:8],
                failure_record_id=failure_id,
                confidence=0.6,
                suggested_action=f"Fix import in {record.module_path or 'unknown module'}",
                affected_files=[record.module_path] if record.module_path else [],
                reasoning="Import errors typically require fixing import statements or dependencies",
                source="error_type_analysis",
            ))
        elif record.failure_type == "assertion":
            suggestions.append(FixSuggestion(
                suggestion_id=str(uuid.uuid4())[:8],
                failure_record_id=failure_id,
                confidence=0.7,
                suggested_action="Review test assertion and expected values",
                affected_files=[record.test_path],
                reasoning="Assertion failures often indicate mismatched expectations",
                source="error_type_analysis",
            ))

        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        self._fix_suggestions[failure_id] = suggestions

        return suggestions

    def mark_fix_applied(self, record_id: str, fix: str, result: str) -> None:
        """Mark that a fix was applied and record the result."""
        if record_id not in self._records:
            return

        record = self._records[record_id]
        updated = TestFailureRecord(
            record_id=record.record_id,
            test_path=record.test_path,
            test_name=record.test_name,
            failure_type=record.failure_type,
            error_message=record.error_message,
            stack_trace=record.stack_trace,
            module_path=record.module_path,
            dependencies_affected=record.dependencies_affected,
            suggested_fix=fix,
            fix_applied=True,
            fix_result=result,
            timestamp=record.timestamp,
            metadata=record.metadata,
        )
        self._records[record_id] = updated

        # Update pattern
        self._update_patterns(updated)

        # Save updated record
        with open(self._get_record_path(record_id), "w", encoding="utf-8") as f:
            f.write(self._serialize_record(updated))

    def analyze_failure_chain(self, test_path: str) -> Dict[str, Any]:
        """Analyze the full chain of failures for a test."""
        chain = self._graph.get_failure_chain(test_path)
        records = [self._records.get(r) for r in chain if r in self._records]

        return {
            "test_path": test_path,
            "chain_length": len(chain),
            "failure_records": [
                {
                    "record_id": r.record_id,
                    "error": r.error_message[:100],
                    "type": r.failure_type,
                    "timestamp": r.timestamp,
                    "fixed": r.fix_applied,
                }
                for r in records
            ],
            "suggestions": self.suggest_fix(chain[0]) if chain else [],
        }

    def get_dependency_graph(self) -> Dict[str, Any]:
        """Get the current dependency graph."""
        return self._graph.to_dict()

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about failures and patterns."""
        total_records = len(self._records)
        fixed_records = sum(1 for r in self._records.values() if r.fix_applied)
        patterns_count = len(self._patterns)

        # Count by failure type
        by_type: Dict[str, int] = {}
        for record in self._records.values():
            by_type[record.failure_type] = by_type.get(record.failure_type, 0) + 1

        # Count recurring patterns
        recurring = sum(1 for p in self._patterns.values() if p.frequency > 1)

        return {
            "total_failures": total_records,
            "fixed_failures": fixed_records,
            "fix_rate": fixed_records / total_records if total_records > 0 else 0.0,
            "patterns_identified": patterns_count,
            "recurring_patterns": recurring,
            "by_failure_type": by_type,
        }

    def _load_from_disk(self) -> None:
        """Load records and patterns from disk."""
        if not self.store_path.exists():
            return

        # Load records
        for file in self.store_path.glob("*.jsonl"):
            if file.name.startswith("pattern_"):
                continue
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = f.read().strip()
                    if data:
                        record = self._deserialize_record(data)
                        self._records[record.record_id] = record
                        self._graph.add_node(record.test_path)
                        for dep in record.dependencies_affected:
                            self._graph.add_dependency(record.test_path, dep)
            except Exception:
                continue

        # Load patterns
        for file in self.store_path.glob("pattern_*.jsonl"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = f.read().strip()
                    if data:
                        pattern = json.loads(data)
                        self._patterns[pattern["pattern_id"]] = FailurePattern(**pattern)
            except Exception:
                continue


# Convenience functions
def create_test_memory_layer(path: str | None = None) -> TestCausalMemoryLayer:
    """Create a new TestCausalMemoryLayer."""
    return TestCausalMemoryLayer(Path(path) if path else None)
