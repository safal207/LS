"""
Tests for TestCausalMemoryLayer
"""

import unittest
from pathlib import Path
from codex.test_causal_memory.layer import TestCausalMemoryLayer, TestCausalGraph


class TestTestCausalGraph(unittest.TestCase):
    """Tests for the dependency graph."""

    def test_add_node(self) -> None:
        """Test adding nodes to the graph."""
        graph = TestCausalGraph()
        graph.add_node("test_example.py")
        self.assertIn("test_example.py", graph._nodes)

    def test_add_dependency(self) -> None:
        """Test adding dependencies."""
        graph = TestCausalGraph()
        graph.add_dependency("test_a.py", "codex.module_a", "import")
        self.assertIn("codex.module_a", graph._edges["test_a.py"])

    def test_record_failure(self) -> None:
        """Test recording failures."""
        graph = TestCausalGraph()
        graph.add_node("test_example.py")
        graph.record_failure("test_example.py", "failure_123")
        self.assertIn("failure_123", graph._failures["test_example.py"])

    def test_get_affected_by_failure(self) -> None:
        """Test finding affected nodes."""
        graph = TestCausalGraph()
        graph.add_dependency("test_a.py", "module_x", "import")
        graph.add_dependency("test_b.py", "module_x", "import")

        affected = graph.get_affected_by_failure("module_x")
        self.assertIn("test_a.py", affected)
        self.assertIn("test_b.py", affected)


class TestTestCausalMemoryLayer(unittest.TestCase):
    """Tests for the main memory layer."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_dir = Path("test_memory_unit")
        self.test_dir.mkdir(exist_ok=True)
        self.memory = TestCausalMemoryLayer(self.test_dir)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_record_failure(self) -> None:
        """Test recording a failure."""
        stack_trace = '''Traceback (most recent call last):
  File "tests/unit/test_example.py", line 42, in test_example
    assert result == expected
AssertionError: 5 != 3'''

        record_id = self.memory.record_failure(
            test_path="tests/unit/test_example.py",
            test_name="test_example",
            failure_type="assertion",
            error_message="AssertionError: 5 != 3",
            stack_trace=stack_trace,
            module_path="codex/example/module.py",
        )

        self.assertIsNotNone(record_id)
        self.assertIn(record_id, self.memory._records)
        self.assertEqual(self.memory._records[record_id].test_name, "test_example")

    def test_record_import_failure(self) -> None:
        """Test recording an import failure."""
        stack_trace = '''Traceback (most recent call last):
  File "tests/unit/test_example.py", line 10, in <module>
    from codex.module import Class
ModuleNotFoundError: No module named 'module'
'''

        record_id = self.memory.record_failure(
            test_path="tests/unit/test_import.py",
            test_name="test_import",
            failure_type="import",
            error_message="ModuleNotFoundError: No module named 'module'",
            stack_trace=stack_trace,
            module_path="codex/module.py",
        )

        record = self.memory._records[record_id]
        self.assertEqual(record.failure_type, "import")
        # Should extract the dependency
        self.assertTrue(len(record.dependencies_affected) > 0)

    def test_suggest_fix_pattern_match(self) -> None:
        """Test fix suggestions based on pattern matching."""
        # Record first failure
        id1 = self.memory.record_failure(
            test_path="tests/unit/test_a.py",
            test_name="test_a",
            failure_type="assertion",
            error_message="Expected True but got False",
        )

        # Record same failure again
        id2 = self.memory.record_failure(
            test_path="tests/unit/test_b.py",
            test_name="test_b",
            failure_type="assertion",
            error_message="Expected True but got False",
        )

        # Mark first as fixed successfully
        self.memory.mark_fix_applied(id1, "Changed condition logic", "success")

        # Get suggestions for second
        suggestions = self.memory.suggest_fix(id2)

        # Should have pattern-based suggestion
        pattern_suggestions = [s for s in suggestions if s.source == "pattern_match"]
        self.assertTrue(len(pattern_suggestions) > 0)
        self.assertEqual(pattern_suggestions[0].confidence, 1.0)

    def test_suggest_fix_dependency_analysis(self) -> None:
        """Test fix suggestions based on dependency analysis."""
        # Create a failure chain
        id1 = self.memory.record_failure(
            test_path="tests/unit/test_bottom.py",
            test_name="test_bottom",
            failure_type="import",
            error_message="Import error",
            stack_trace='''Traceback (most recent call last):
  File "tests/unit/test_bottom.py", line 5, in <module>
    from codex.middle import Middle
  File "codex/middle.py", line 10, in <module>
    from codex.bottom import Bottom
  File "codex/bottom.py", line 1, in <module>
    import missing_module
''',
        )

        suggestions = self.memory.suggest_fix(id1)

        # Should have dependency-based suggestion
        dep_suggestions = [s for s in suggestions if s.source == "dependency_analysis"]
        self.assertTrue(len(dep_suggestions) > 0)

    def test_mark_fix_applied(self) -> None:
        """Test marking a fix as applied."""
        record_id = self.memory.record_failure(
            test_path="tests/unit/test_example.py",
            test_name="test_example",
            failure_type="assertion",
            error_message="Test error",
        )

        self.memory.mark_fix_applied(record_id, "Applied fix", "success")

        record = self.memory._records[record_id]
        self.assertTrue(record.fix_applied)
        self.assertEqual(record.fix_result, "success")
        self.assertEqual(record.suggested_fix, "Applied fix")

    def test_analyze_failure_chain(self) -> None:
        """Test analyzing the failure chain."""
        # Record multiple failures
        id1 = self.memory.record_failure(
            test_path="tests/unit/test_chain.py",
            test_name="test_chain_1",
            failure_type="error",
            error_message="Error in chain",
        )
        id2 = self.memory.record_failure(
            test_path="tests/unit/test_chain.py",
            test_name="test_chain_2",
            failure_type="error",
            error_message="Error in chain 2",
        )

        analysis = self.memory.analyze_failure_chain("tests/unit/test_chain.py")

        self.assertEqual(analysis["test_path"], "tests/unit/test_chain.py")
        self.assertGreaterEqual(analysis["chain_length"], 1)

    def test_get_statistics(self) -> None:
        """Test getting statistics."""
        # Record some failures
        for i in range(3):
            self.memory.record_failure(
                test_path=f"tests/unit/test_{i}.py",
                test_name=f"test_{i}",
                failure_type="assertion",
                error_message=f"Error {i}",
            )

        stats = self.memory.get_statistics()

        self.assertEqual(stats["total_failures"], 3)
        self.assertIn("assertion", stats["by_failure_type"])

    def test_extract_dependencies(self) -> None:
        """Test dependency extraction from stack trace."""
        stack = '''Traceback (most recent call last):
  File "tests/unit/test_example.py", line 10, in test_example
    from codex.module_a import A
  File "codex/module_a.py", line 5, in <module>
    from codex.module_b import B
  File "codex/module_b.py", line 3, in <module>
    import missing_module'''

        deps = self.memory._extract_dependencies(stack)

        self.assertTrue(any("codex.module_a" in d for d in deps))
        self.assertTrue(any("codex.module_b" in d for d in deps))

    def test_persistence(self) -> None:
        """Test that data persists after reload."""
        # Record a failure
        self.memory.record_failure(
            test_path="tests/unit/test_persist.py",
            test_name="test_persist",
            failure_type="assertion",
            error_message="Persistent error",
        )

        # Create new layer with same path
        new_memory = TestCausalMemoryLayer(self.test_dir)

        # Should have loaded the record
        self.assertEqual(len(new_memory._records), 1)
        self.assertIn(list(self.memory._records.keys())[0], new_memory._records)


if __name__ == "__main__":
    unittest.main()
