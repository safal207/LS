import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from llm.breaker import CircuitBreaker, CircuitOpenError


class TestCircuitBreaker(unittest.TestCase):
    def test_open_after_failures(self):
        breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
        breaker.after_failure(RuntimeError("boom"))
        breaker.after_failure(RuntimeError("boom"))
        with self.assertRaises(CircuitOpenError):
            breaker.before_call()


if __name__ == "__main__":
    unittest.main()
